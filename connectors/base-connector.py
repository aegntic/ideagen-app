"""
Base Fivetran Connector
Shared functionality for all IdeaGen Fivetran connectors
"""

import asyncio
import logging
import json
import time
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional, Union
from abc import ABC, abstractmethod
import backoff
from dataclasses import dataclass, asdict

# Fivetran SDK imports
try:
    from fivetran_client import FivetranClient
    from fivetran_client.models import (
        ConnectorSchemaRequest,
        ConnectorSchemaResponse,
        ConnectorDataRequest,
        ConnectorDataResponse,
        Table,
        Column,
        DataType
    )
except ImportError:
    # Fallback for development without Fivetran SDK
    class FivetranClient:
        def __init__(self, api_key: str, api_secret: str):
            self.api_key = api_key
            self.api_secret = api_secret

    # Mock classes for development
    class ConnectorSchemaRequest: pass
    class ConnectorSchemaResponse: pass
    class ConnectorDataRequest: pass
    class ConnectorDataResponse: pass
    class Table: pass
    class Column: pass
    class DataType: pass


logger = logging.getLogger(__name__)


@dataclass
class ConnectorConfig:
    """Base configuration for all connectors"""
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    rate_limit_per_minute: int = 60
    batch_size: int = 100
    enable_debug: bool = False


@dataclass
class DataRecord:
    """Standard data record structure"""
    id: str
    data: Dict[str, Any]
    timestamp: datetime
    source: str
    metadata: Optional[Dict[str, Any]] = None


class BaseConnector(ABC):
    """
    Abstract base class for all Fivetran connectors
    Provides shared functionality for schema definition, data extraction,
    error handling, retry logic, and configuration management
    """

    def __init__(self, config: ConnectorConfig = None):
        self.config = config or ConnectorConfig()
        self.logger = self._setup_logger()
        self.rate_limiter = RateLimiter(self.config.rate_limit_per_minute)

        # Initialize Fivetran client if credentials provided
        if self.config.api_key and self.config.api_secret:
            self.fivetran_client = FivetranClient(
                api_key=self.config.api_key,
                api_secret=self.config.api_secret
            )
        else:
            self.fivetran_client = None
            self.logger.warning("No Fivetran credentials provided - running in development mode")

    def _setup_logger(self) -> logging.Logger:
        """Setup logger with appropriate level and formatting"""
        logger = logging.getLogger(self.__class__.__name__)
        if self.config.enable_debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    @abstractmethod
    async def get_tables(self) -> List[Table]:
        """Define the tables this connector provides"""
        pass

    @abstractmethod
    async def extract_data(self, table_name: str, cursor: Optional[str] = None) -> List[DataRecord]:
        """Extract data for a specific table"""
        pass

    @abstractmethod
    def get_cursor(self, record: DataRecord) -> str:
        """Generate cursor value for a record"""
        pass

    @backoff.on_exception(
        backoff.expo,
        (Exception,),
        max_tries=3,
        base=1,
        max_value=60
    )
    async def get_schema(self) -> ConnectorSchemaResponse:
        """
        Define the connector schema for Fivetran
        """
        try:
            self.logger.info(f"Defining {self.__class__.__name__} schema")
            tables = await self.get_tables()

            # Create schema response
            schema_response = ConnectorSchemaResponse()
            schema_response.tables = tables
            schema_response.connector_version = "1.0.0"

            self.logger.info(f"Schema defined with {len(tables)} tables")
            return schema_response

        except Exception as e:
            self.logger.error(f"Error defining schema: {str(e)}")
            raise

    @backoff.on_exception(
        backoff.expo,
        (Exception,),
        max_tries=3,
        base=1,
        max_value=60
    )
    async def get_data(self, request: ConnectorDataRequest) -> ConnectorDataResponse:
        """
        Extract data for Fivetran
        """
        try:
            self.logger.info(f"Extracting data for table: {request.table_name}")

            # Apply rate limiting
            await self.rate_limiter.acquire()

            # Extract data
            records = await self.extract_data(
                table_name=request.table_name,
                cursor=request.cursor
            )

            # Transform to Fivetran format
            data_response = ConnectorDataResponse()
            data_response.rows = []
            data_response.has_more = False

            for record in records:
                # Convert to Fivetran row format
                row = {
                    'id': record.id,
                    'data': record.data,
                    'timestamp': record.timestamp.isoformat(),
                    'source': record.source,
                    'metadata': record.metadata or {}
                }
                data_response.rows.append(row)

                # Set cursor for next page
                if not data_response.cursor or self.compare_cursors(
                    self.get_cursor(record), data_response.cursor
                ) > 0:
                    data_response.cursor = self.get_cursor(record)

            # Determine if there's more data
            if len(records) >= self.config.batch_size:
                data_response.has_more = True

            self.logger.info(f"Extracted {len(records)} records")
            return data_response

        except Exception as e:
            self.logger.error(f"Error extracting data: {str(e)}")
            raise

    def compare_cursors(self, cursor1: str, cursor2: str) -> int:
        """Compare two cursor values. Returns 1 if cursor1 > cursor2, -1 if <, 0 if equal"""
        try:
            # Try to compare as timestamps
            dt1 = datetime.fromisoformat(cursor1.replace('Z', '+00:00'))
            dt2 = datetime.fromisoformat(cursor2.replace('Z', '+00:00'))

            if dt1 > dt2:
                return 1
            elif dt1 < dt2:
                return -1
            else:
                return 0
        except:
            # Fallback to string comparison
            if cursor1 > cursor2:
                return 1
            elif cursor1 < cursor2:
                return -1
            else:
                return 0

    def create_table(self, name: str, columns: List[Column]) -> Table:
        """Create a table definition"""
        table = Table()
        table.name = name
        table.columns = columns
        table.primary_key = [col.name for col in columns if col.primary_key]
        return table

    def create_column(
        self,
        name: str,
        data_type: DataType,
        primary_key: bool = False,
        nullable: bool = True,
        description: Optional[str] = None
    ) -> Column:
        """Create a column definition"""
        column = Column()
        column.name = name
        column.data_type = data_type
        column.primary_key = primary_key
        column.nullable = nullable
        column.description = description
        return column

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the connector"""
        try:
            # Test basic connectivity
            start_time = time.time()

            # Test schema extraction
            schema = await self.get_schema()

            end_time = time.time()

            return {
                'status': 'healthy',
                'response_time_ms': (end_time - start_time) * 1000,
                'tables_count': len(schema.tables) if schema.tables else 0,
                'timestamp': datetime.now(UTC).isoformat(),
                'connector_version': '1.0.0'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now(UTC).isoformat(),
                'connector_version': '1.0.0'
            }

    def validate_config(self) -> List[str]:
        """Validate connector configuration and return list of errors"""
        errors = []

        if not self.config.api_key:
            errors.append("API key is required")

        if not self.config.api_secret:
            errors.append("API secret is required")

        if self.config.timeout <= 0:
            errors.append("Timeout must be positive")

        if self.config.retry_attempts < 0:
            errors.append("Retry attempts must be non-negative")

        return errors

    async def cleanup(self):
        """Cleanup resources"""
        if self.fivetran_client:
            # Add any Fivetran client cleanup here
            pass
        self.logger.info("Connector cleanup completed")


class RateLimiter:
    """Simple rate limiter implementation"""

    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests = []
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Acquire rate limit"""
        async with self.lock:
            now = time.time()
            minute_ago = now - 60

            # Remove old requests
            self.requests = [req_time for req_time in self.requests if req_time > minute_ago]

            # Check if we can make a request
            if len(self.requests) >= self.requests_per_minute:
                # Calculate wait time
                oldest_request = min(self.requests)
                wait_time = 60 - (now - oldest_request)

                if wait_time > 0:
                    self.logger.warning(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                    await asyncio.sleep(wait_time)

            # Record this request
            self.requests.append(now)


class DataTransformer:
    """Utility class for transforming data"""

    @staticmethod
    def sanitize_text(text: str) -> str:
        """Sanitize text data"""
        if not text:
            return ""
        return text.strip().replace('\x00', '')

    @staticmethod
    def normalize_timestamp(timestamp: Union[str, datetime, int, float]) -> datetime:
        """Normalize various timestamp formats to datetime"""
        if isinstance(timestamp, datetime):
            return timestamp
        elif isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp, UTC)
        elif isinstance(timestamp, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                # Try Unix timestamp
                try:
                    return datetime.fromtimestamp(float(timestamp), UTC)
                except:
                    # Default to current time
                    return datetime.now(UTC)
        else:
            return datetime.now(UTC)

    @staticmethod
    def extract_domain(url: str) -> Optional[str]:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return None

    @staticmethod
    def clean_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and normalize metadata"""
        if not metadata:
            return {}

        cleaned = {}
        for key, value in metadata.items():
            # Convert keys to lowercase
            clean_key = str(key).lower().strip()

            # Handle different value types
            if isinstance(value, (str, int, float, bool)):
                cleaned[clean_key] = value
            elif isinstance(value, dict):
                cleaned[clean_key] = DataTransformer.clean_metadata(value)
            elif isinstance(value, list):
                cleaned[clean_key] = [
                    DataTransformer.clean_metadata(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                cleaned[clean_key] = str(value)

        return cleaned


# Error classes
class ConnectorError(Exception):
    """Base connector error"""
    pass


class ConfigurationError(ConnectorError):
    """Configuration related error"""
    pass


class AuthenticationError(ConnectorError):
    """Authentication related error"""
    pass


class RateLimitError(ConnectorError):
    """Rate limit related error"""
    pass


class DataExtractionError(ConnectorError):
    """Data extraction related error"""
    pass