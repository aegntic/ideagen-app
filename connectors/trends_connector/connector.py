"""
Fivetran Google Trends Connector
Main connector implementation using Fivetran SDK
"""

import asyncio
import logging
import json
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional
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

from .trends_client import TrendsClient
from .config import get_config, (
    TREND_SCHEMA, RELATED_QUERY_SCHEMA, TRENDING_TOPIC_SCHEMA,
    REGION_TREND_SCHEMA, CATEGORY_TREND_SCHEMA
)


logger = logging.getLogger(__name__)


class TrendsConnector:
    """
    Fivetran connector for Google Trends data extraction
    Handles schema definition, data extraction, and synchronization
    """

    def __init__(self, config=None):
        self.config = config or get_config()
        self.trends_client = TrendsClient(self.config)
        self.fivetran_client = FivetranClient(
            api_key=self.config.fivetran_api_key,
            api_secret=self.config.fivetran_api_secret
        )
        self.logger = logger

    async def get_schema(self) -> ConnectorSchemaResponse:
        """
        Define the connector schema for Fivetran
        """
        try:
            self.logger.info("Defining Google Trends connector schema")

            tables = []

            # Trends table
            trends_table = Table(
                name="trends_keyword_interest",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in TREND_SCHEMA.items()
                ]
            )
            tables.append(trends_table)

            # Related queries table
            related_queries_table = Table(
                name="trends_related_queries",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in RELATED_QUERY_SCHEMA.items()
                ]
            )
            tables.append(related_queries_table)

            # Trending topics table
            trending_topics_table = Table(
                name="trends_trending_topics",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in TRENDING_TOPIC_SCHEMA.items()
                ]
            )
            tables.append(trending_topics_table)

            # Regional trends table
            regional_trends_table = Table(
                name="trends_regional_interest",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in REGION_TREND_SCHEMA.items()
                ]
            )
            tables.append(regional_trends_table)

            # Category trends table
            category_trends_table = Table(
                name="trends_category_trends",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in CATEGORY_TREND_SCHEMA.items()
                ]
            )
            tables.append(category_trends_table)

            return ConnectorSchemaResponse(
                tables=tables,
                schema=self.config.destination_schema
            )

        except Exception as e:
            self.logger.error(f"Error defining schema: {e}")
            raise

    async def sync_data(self, state: Optional[Dict[str, Any]] = None) -> ConnectorDataResponse:
        """
        Synchronize data from Google Trends to Fivetran destination
        """
        try:
            self.logger.info("Starting Google Trends data synchronization")

            # Initialize state if not provided
            if state is None:
                state = {
                    "last_sync": None,
                    "processed_trends": set(),
                    "processed_queries": set(),
                    "processed_topics": set(),
                    "processed_regions": set(),
                    "processed_categories": set(),
                    "cursor": {}
                }

            current_time = datetime.now(UTC)
            sync_data = {
                "trends": [],
                "related_queries": [],
                "trending_topics": [],
                "regional_trends": [],
                "category_trends": []
            }

            # Sync category trends first
            await self._sync_category_trends(state, sync_data)

            # Sync trending topics
            await self._sync_trending_topics(state, sync_data)

            # Sync keyword trends for high-value categories
            await self._sync_keyword_trends(state, sync_data)

            # Sync related queries for top keywords
            await self._sync_related_queries(state, sync_data)

            # Sync regional trends
            await self._sync_regional_trends(state, sync_data)

            # Update state
            state["last_sync"] = current_time.isoformat()

            # Send data to Fivetran
            await self._send_data_to_fivetran(sync_data)

            return ConnectorDataResponse(
                has_more=False,
                state=state,
                records_processed=len(sync_data["trends"]) + len(sync_data["related_queries"]) +
                               len(sync_data["trending_topics"]) + len(sync_data["regional_trends"]) +
                               len(sync_data["category_trends"])
            )

        except Exception as e:
            self.logger.error(f"Error during data synchronization: {e}")
            raise

    async def _sync_category_trends(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize trends for predefined business categories"""
        self.logger.info("Syncing category trends")

        # Define keywords for each category
        category_keywords_map = {
            "AI/Machine Learning": ["artificial intelligence", "machine learning", "AI tools", "ChatGPT", "GPT"],
            "Productivity Tools": ["productivity software", "task management", "workflow automation", "productivity apps"],
            "SaaS Platforms": ["software as a service", "SaaS platform", "cloud software", "subscription software"],
            "FinTech": ["financial technology", "fintech apps", "digital banking", "payment solutions"],
            "HealthTech": ["health technology", "digital health", "medical software", "healthcare apps"],
            "E-commerce": ["online shopping", "e-commerce platform", "retail technology", "online marketplace"],
            "Remote Work": ["remote work tools", "virtual collaboration", "work from home", "distributed teams"],
            "Sustainability": ["sustainable technology", "green tech", "climate tech", "environmental solutions"]
        }

        for category_name, keywords in category_keywords_map.items():
            try:
                category_id = f"cat_{category_name.lower().replace(' ', '_').replace('/', '_')}"

                if category_id in state["processed_categories"]:
                    continue

                async for trend_data in self.trends_client.get_category_trends(
                    category_keywords=keywords[:3],  # Limit to top 3 keywords per category
                    category_name=category_name
                ):
                    trend_id = f"{trend_data['id']}"
                    if trend_id not in state["processed_trends"]:
                        sync_data["category_trends"].append(trend_data)
                        state["processed_trends"].add(trend_id)

                state["processed_categories"].add(category_id)

            except Exception as e:
                self.logger.warning(f"Error syncing category {category_name}: {e}")
                continue

    async def _sync_trending_topics(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize currently trending topics"""
        self.logger.info("Syncing trending topics")

        try:
            async for topic_data in self.trends_client.get_trending_topics(
                regions=self.config.regions,
                limit=self.config.trending_topics_limit
            ):
                topic_id = topic_data["id"]

                # Skip if already processed
                if topic_id in state["processed_topics"]:
                    continue

                # Include all trending topics
                sync_data["trending_topics"].append(topic_data)
                state["processed_topics"].add(topic_id)

        except Exception as e:
            self.logger.error(f"Error syncing trending topics: {e}")

    async def _sync_keyword_trends(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize trends for high-value keywords"""
        self.logger.info("Syncing keyword trends")

        # High-value keywords for idea generation
        high_value_keywords = [
            "AI automation", "productivity app", "SaaS platform", "fintech solution",
            "healthcare technology", "e-commerce platform", "remote work tool",
            "sustainability software", "machine learning", "API integration",
            "data analytics", "cloud computing", "mobile app", "blockchain technology"
        ]

        try:
            async for trend_data in self.trends_client.get_keyword_trends(
                keywords=high_value_keywords
            ):
                trend_id = trend_data["id"]

                # Skip if already processed
                if trend_id in state["processed_trends"]:
                    continue

                # Only include trends with good idea potential
                if trend_data.get("idea_potential", 0) >= 0.3:
                    sync_data["trends"].append(trend_data)
                    state["processed_trends"].add(trend_id)

        except Exception as e:
            self.logger.error(f"Error syncing keyword trends: {e}")

    async def _sync_related_queries(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize related queries for top performing keywords"""
        self.logger.info("Syncing related queries")

        # Top keywords from recent trends (would be determined from trend analysis)
        top_keywords = [
            "AI automation", "productivity software", "SaaS", "fintech",
            "healthcare technology", "remote work tools"
        ]

        for keyword in top_keywords:
            try:
                async for query_data in self.trends_client.get_related_queries(
                    keyword=keyword,
                    limit=self.config.related_queries_limit
                ):
                    query_id = query_data["id"]

                    # Skip if already processed
                    if query_id in state["processed_queries"]:
                        continue

                    # Include queries with good opportunity score
                    if query_data.get("opportunity_score", 0) >= 0.4:
                        sync_data["related_queries"].append(query_data)
                        state["processed_queries"].add(query_id)

            except Exception as e:
                self.logger.warning(f"Error syncing related queries for {keyword}: {e}")
                continue

    async def _sync_regional_trends(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize regional trend data"""
        self.logger.info("Syncing regional trends")

        # Key keywords for regional analysis
        regional_keywords = [
            "AI automation", "productivity tools", "fintech", "healthcare technology"
        ]

        for keyword in regional_keywords:
            try:
                async for regional_data in self.trends_client.get_regional_trends(
                    keyword=keyword,
                    regions=self.config.regions
                ):
                    regional_id = regional_data["id"]

                    # Skip if already processed
                    if regional_id in state["processed_regions"]:
                        continue

                    # Include regional data with localization opportunities
                    if regional_data.get("localization_opportunity", False):
                        sync_data["regional_trends"].append(regional_data)
                        state["processed_regions"].add(regional_id)

            except Exception as e:
                self.logger.warning(f"Error syncing regional trends for {keyword}: {e}")
                continue

    async def _send_data_to_fivetran(self, sync_data: Dict[str, List]):
        """Send synchronized data to Fivetran destination"""
        try:
            # Send trends data
            if sync_data["trends"]:
                await self._send_table_data("trends_keyword_interest", sync_data["trends"])
                self.logger.info(f"Sent {len(sync_data['trends'])} trend records to Fivetran")

            # Send related queries data
            if sync_data["related_queries"]:
                await self._send_table_data("trends_related_queries", sync_data["related_queries"])
                self.logger.info(f"Sent {len(sync_data['related_queries'])} related query records to Fivetran")

            # Send trending topics data
            if sync_data["trending_topics"]:
                await self._send_table_data("trends_trending_topics", sync_data["trending_topics"])
                self.logger.info(f"Sent {len(sync_data['trending_topics'])} trending topic records to Fivetran")

            # Send regional trends data
            if sync_data["regional_trends"]:
                await self._send_table_data("trends_regional_interest", sync_data["regional_trends"])
                self.logger.info(f"Sent {len(sync_data['regional_trends'])} regional trend records to Fivetran")

            # Send category trends data
            if sync_data["category_trends"]:
                await self._send_table_data("trends_category_trends", sync_data["category_trends"])
                self.logger.info(f"Sent {len(sync_data['category_trends'])} category trend records to Fivetran")

        except Exception as e:
            self.logger.error(f"Error sending data to Fivetran: {e}")
            raise

    async def _send_table_data(self, table_name: str, data: List[Dict[str, Any]]):
        """Send data for a specific table to Fivetran"""
        try:
            # Convert data to Fivetran format
            fivetran_data = []
            for record in data:
                # Flatten nested objects and convert lists to strings
                flattened_record = {}
                for key, value in record.items():
                    if isinstance(value, (list, dict)):
                        flattened_record[key] = json.dumps(value)
                    else:
                        flattened_record[key] = value
                fivetran_data.append(flattened_record)

            # Send data using Fivetran client
            # This would use the actual Fivetran SDK in production
            # await self.fivetran_client.upsert_data(
            #     schema=self.config.destination_schema,
            #     table=table_name,
            #     data=fivetran_data
            # )

        except Exception as e:
            self.logger.error(f"Error sending data for table {table_name}: {e}")
            raise

    async def test_connection(self) -> bool:
        """Test connection to Google Trends"""
        try:
            self.logger.info("Testing Google Trends connection")

            # Try to fetch a simple trending search to test connection
            trending_data = self.trends_client.pytrends.trending_searches(pn='US')

            if trending_data is not None and not trending_data.empty:
                self.logger.info(f"Google Trends connection test successful - found {len(trending_data)} trending topics")
                return True
            else:
                self.logger.error("Google Trends connection test failed - no data returned")
                return False

        except Exception as e:
            self.logger.error(f"Google Trends connection test failed: {e}")
            return False

    async def get_data_samples(self, limit: int = 3) -> Dict[str, List[Dict[str, Any]]]:
        """Get sample data for testing and validation"""
        try:
            self.logger.info(f"Getting {limit} sample records from each data type")

            samples = {
                "trends": [],
                "related_queries": [],
                "trending_topics": [],
                "regional_trends": [],
                "category_trends": []
            }

            # Get sample trending topics
            topic_count = 0
            async for topic_data in self.trends_client.get_trending_topics(limit=limit):
                samples["trending_topics"].append(topic_data)
                topic_count += 1
                if topic_count >= limit:
                    break

            # Get sample keyword trends
            test_keywords = ["AI automation", "productivity tools"]
            trend_count = 0
            async for trend_data in self.trends_client.get_keyword_trends(
                keywords=test_keywords,
                timeframe="today 7d"  # Last 7 days
            ):
                samples["trends"].append(trend_data)
                trend_count += 1
                if trend_count >= limit:
                    break

            # Get sample related queries
            if test_keywords:
                query_count = 0
                async for query_data in self.trends_client.get_related_queries(
                    keyword=test_keywords[0],
                    limit=limit
                ):
                    samples["related_queries"].append(query_data)
                    query_count += 1
                    if query_count >= limit:
                        break

            # Get sample regional trends
            if test_keywords:
                regional_count = 0
                async for regional_data in self.trends_client.get_regional_trends(
                    keyword=test_keywords[0],
                    regions=["US", "CA"]
                ):
                    samples["regional_trends"].append(regional_data)
                    regional_count += 1
                    if regional_count >= limit:
                        break

            # Get sample category trends
            category_count = 0
            async for category_data in self.trends_client.get_category_trends(
                category_keywords=["artificial intelligence", "machine learning"],
                category_name="AI/Machine Learning",
                timeframe="today 7d"
            ):
                samples["category_trends"].append(category_data)
                category_count += 1
                if category_count >= limit:
                    break

            return samples

        except Exception as e:
            self.logger.error(f"Error getting data samples: {e}")
            raise

    def get_connector_info(self) -> Dict[str, Any]:
        """Get connector information and configuration"""
        return {
            "name": "Google Trends Connector",
            "version": "1.0.0",
            "description": "Extracts trending keywords, related queries, and regional data from Google Trends for idea generation",
            "source_type": "API",
            "sync_frequency": f"{self.config.sync_frequency_hours} hours",
            "supported_data_types": [
                "keyword_trends", "related_queries", "trending_topics",
                "regional_trends", "category_trends"
            ],
            "configuration": {
                "timezone": self.config.timezone,
                "geo": self.config.geo,
                "language": self.config.language,
                "categories": self.config.categories,
                "keywords_limit": self.config.keywords_limit,
                "timeframe_days": self.config.timeframe_days,
                "destination_schema": self.config.destination_schema
            },
            "features": [
                "Idea potential scoring",
                "Market demand assessment",
                "Growth rate analysis",
                "Volatility measurement",
                "Regional opportunity detection",
                "Category trend analysis",
                "Business opportunity assessment",
                "Innovation potential evaluation"
            ]
        }


async def main():
    """Main entry point for the connector"""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Initialize connector
        connector = TrendsConnector()

        # Parse command line arguments
        if len(sys.argv) > 1:
            command = sys.argv[1].lower()

            if command == "schema":
                schema = await connector.get_schema()
                print("Connector Schema:")
                print(json.dumps(schema.dict(), indent=2))

            elif command == "sync":
                result = await connector.sync_data()
                print(f"Sync completed: {result.records_processed} records processed")

            elif command == "test":
                is_connected = await connector.test_connection()
                print(f"Connection test: {'PASSED' if is_connected else 'FAILED'}")

            elif command == "sample":
                samples = await connector.get_data_samples()
                print("Sample Data:")
                print(json.dumps(samples, indent=2))

            elif command == "info":
                info = connector.get_connector_info()
                print("Connector Information:")
                print(json.dumps(info, indent=2))

            else:
                print(f"Unknown command: {command}")
                print("Available commands: schema, sync, test, sample, info")
        else:
            print("Google Trends Connector for Fivetran")
            print("Usage: python -m trends_connector.main [command]")
            print("Commands: schema, sync, test, sample, info")

    except Exception as e:
        logger.error(f"Connector error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())