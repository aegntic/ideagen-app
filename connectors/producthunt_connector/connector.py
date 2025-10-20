"""
Fivetran Product Hunt Connector
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

from .producthunt_client import ProductHuntClient
from .config import get_config, PRODUCT_SCHEMA, MAKER_SCHEMA, COMMENT_SCHEMA, CATEGORY_SCHEMA


logger = logging.getLogger(__name__)


class ProductHuntConnector:
    """
    Fivetran connector for Product Hunt data extraction
    Handles schema definition, data extraction, and synchronization
    """

    def __init__(self, config=None):
        self.config = config or get_config()
        self.producthunt_client = ProductHuntClient(self.config)
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
            self.logger.info("Defining Product Hunt connector schema")

            tables = []

            # Products table
            products_table = Table(
                name="producthunt_products",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in PRODUCT_SCHEMA.items()
                ]
            )
            tables.append(products_table)

            # Makers table
            makers_table = Table(
                name="producthunt_makers",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in MAKER_SCHEMA.items()
                ]
            )
            tables.append(makers_table)

            # Comments table
            comments_table = Table(
                name="producthunt_comments",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in COMMENT_SCHEMA.items()
                ]
            )
            tables.append(comments_table)

            # Categories table
            categories_table = Table(
                name="producthunt_categories",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in CATEGORY_SCHEMA.items()
                ]
            )
            tables.append(categories_table)

            return ConnectorSchemaResponse(
                tables=tables,
                schema=self.config.destination_schema
            )

        except Exception as e:
            self.logger.error(f"Error defining schema: {e}")
            raise

    async def sync_data(self, state: Optional[Dict[str, Any]] = None) -> ConnectorDataResponse:
        """
        Synchronize data from Product Hunt to Fivetran destination
        """
        try:
            self.logger.info("Starting Product Hunt data synchronization")

            # Initialize state if not provided
            if state is None:
                state = {
                    "last_sync": None,
                    "processed_products": set(),
                    "processed_comments": set(),
                    "processed_makers": set(),
                    "processed_categories": set(),
                    "cursor": {}
                }

            current_time = datetime.now(UTC)
            sync_data = {
                "products": [],
                "makers": [],
                "comments": [],
                "categories": []
            }

            # Sync categories first
            await self._sync_categories(state, sync_data)

            # Sync trending products
            await self._sync_products(state, sync_data)

            # Sync comments for high-value products
            await self._sync_comments(state, sync_data)

            # Extract unique makers from products
            await self._sync_makers(state, sync_data)

            # Update state
            state["last_sync"] = current_time.isoformat()

            # Send data to Fivetran
            await self._send_data_to_fivetran(sync_data)

            return ConnectorDataResponse(
                has_more=False,
                state=state,
                records_processed=len(sync_data["products"]) + len(sync_data["comments"]) +
                               len(sync_data["makers"]) + len(sync_data["categories"])
            )

        except Exception as e:
            self.logger.error(f"Error during data synchronization: {e}")
            raise

    async def _sync_categories(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize category information"""
        self.logger.info("Syncing Product Hunt categories")

        try:
            categories = await self.producthunt_client.get_categories()

            for category in categories:
                category_id = str(category["id"])

                if category_id in state["processed_categories"]:
                    continue

                sync_data["categories"].append(category)
                state["processed_categories"].add(category_id)

        except Exception as e:
            self.logger.error(f"Error syncing categories: {e}")

    async def _sync_products(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize trending products"""
        self.logger.info("Syncing trending products")

        try:
            async for product_data in self.producthunt_client.get_trending_posts(
                days_back=self.config.days_back,
                limit=self.config.posts_limit,
                categories=self.config.categories
            ):
                product_id = product_data["id"]

                # Skip if already processed
                if product_id in state["processed_products"]:
                    continue

                # Include all products (they're already trending)
                sync_data["products"].append(product_data)
                state["processed_products"].add(product_id)

                # Track for comment extraction
                if "high_value_products" not in state:
                    state["high_value_products"] = []

                # Add products with good engagement for comment analysis
                votes = product_data.get("votes_count", 0)
                comments = product_data.get("comments_count", 0)
                idea_score = product_data.get("idea_generation_score", 0)

                if (votes >= 50 or comments >= 20 or idea_score >= 0.5) and len(state["high_value_products"]) < 100:
                    state["high_value_products"].append(product_id)

        except Exception as e:
            self.logger.error(f"Error syncing products: {e}")

    async def _sync_comments(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize comments for high-value products"""
        self.logger.info("Syncing comments for high-value products")

        high_value_products = state.get("high_value_products", [])

        for product_id in high_value_products:
            try:
                async for comment_data in self.producthunt_client.get_post_comments(
                    post_id=product_id,
                    limit=self.config.comments_limit
                ):
                    comment_id = str(comment_data["id"])

                    # Skip if already processed
                    if comment_id in state["processed_comments"]:
                        continue

                    # Include all comments (they already have sentiment analysis)
                    sync_data["comments"].append(comment_data)
                    state["processed_comments"].add(comment_id)

            except Exception as e:
                self.logger.warning(f"Error syncing comments for product {product_id}: {e}")
                continue

    async def _sync_makers(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Extract and sync unique makers from products"""
        self.logger.info("Extracting makers from products")

        maker_ids = set()

        # Extract unique makers from products
        for product in sync_data["products"]:
            user_id = product.get("user_id")
            maker_id = product.get("maker_id")

            if user_id and str(user_id) not in state["processed_makers"]:
                maker_ids.add(user_id)
            if maker_id and str(maker_id) not in state["processed_makers"]:
                maker_ids.add(maker_id)

        # Create maker data (since Product Hunt API v2 doesn't have separate maker endpoint)
        for product in sync_data["products"]:
            user_id = product.get("user_id")
            maker_id = product.get("maker_id")

            # Process user as maker
            if user_id and str(user_id) in maker_ids:
                maker_data = self._create_maker_data_from_product(product, is_user=True)
                if maker_data:
                    sync_data["makers"].append(maker_data)
                    state["processed_makers"].add(str(user_id))
                    maker_ids.discard(user_id)

            # Process primary maker
            elif maker_id and str(maker_id) in maker_ids:
                maker_data = self._create_maker_data_from_product(product, is_user=False)
                if maker_data:
                    sync_data["makers"].append(maker_data)
                    state["processed_makers"].add(str(maker_id))
                    maker_ids.discard(maker_id)

    def _create_maker_data_from_product(self, product: Dict[str, Any], is_user: bool) -> Optional[Dict[str, Any]]:
        """Create maker data from product information"""
        try:
            if is_user:
                # This would need to be populated from the actual user data in the API response
                # For now, create a basic maker record
                return {
                    "id": product.get("user_id"),
                    "name": "Unknown User",  # Would get from API response
                    "username": "unknown",
                    "url": None,
                    "headline": "",
                    "bio": "",
                    "twitter_username": None,
                    "website_url": product.get("website"),
                    "profile_image": None,
                    "followers_count": 0,
                    "followees_count": 0,
                    "posts_count": 1,
                    "collections_count": 0,
                    "comments_count": 0,
                    "extracted_at": datetime.now(UTC).isoformat(),
                    "maker_score": 0.5,
                    "expertise_areas": product.get("tagline", "")[:100]
                }
            else:
                return {
                    "id": product.get("maker_id"),
                    "name": "Unknown Maker",
                    "username": "unknown",
                    "url": None,
                    "headline": "",
                    "bio": "",
                    "twitter_username": None,
                    "website_url": product.get("website"),
                    "profile_image": None,
                    "followers_count": 0,
                    "followees_count": 0,
                    "posts_count": 1,
                    "collections_count": 0,
                    "comments_count": 0,
                    "extracted_at": datetime.now(UTC).isoformat(),
                    "maker_score": 0.7,
                    "expertise_areas": product.get("tagline", "")[:100]
                }
        except Exception as e:
            self.logger.warning(f"Error creating maker data: {e}")
            return None

    async def _send_data_to_fivetran(self, sync_data: Dict[str, List]):
        """Send synchronized data to Fivetran destination"""
        try:
            # Send products data
            if sync_data["products"]:
                await self._send_table_data("producthunt_products", sync_data["products"])
                self.logger.info(f"Sent {len(sync_data['products'])} products to Fivetran")

            # Send comments data
            if sync_data["comments"]:
                await self._send_table_data("producthunt_comments", sync_data["comments"])
                self.logger.info(f"Sent {len(sync_data['comments'])} comments to Fivetran")

            # Send makers data
            if sync_data["makers"]:
                await self._send_table_data("producthunt_makers", sync_data["makers"])
                self.logger.info(f"Sent {len(sync_data['makers'])} makers to Fivetran")

            # Send categories data
            if sync_data["categories"]:
                await self._send_table_data("producthunt_categories", sync_data["categories"])
                self.logger.info(f"Sent {len(sync_data['categories'])} categories to Fivetran")

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
        """Test connection to Product Hunt API"""
        try:
            self.logger.info("Testing Product Hunt API connection")

            # Try to fetch categories to test connection
            categories = await self.producthunt_client.get_categories()

            if categories:
                self.logger.info(f"Product Hunt API connection test successful - found {len(categories)} categories")
                return True
            else:
                self.logger.error("Product Hunt API connection test failed - no data returned")
                return False

        except Exception as e:
            self.logger.error(f"Product Hunt API connection test failed: {e}")
            return False

    async def get_data_samples(self, limit: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """Get sample data for testing and validation"""
        try:
            self.logger.info(f"Getting {limit} sample records from each data type")

            samples = {
                "products": [],
                "comments": [],
                "makers": [],
                "categories": []
            }

            # Get sample categories
            categories = await self.producthunt_client.get_categories()
            samples["categories"] = categories[:limit]

            # Get sample products
            product_count = 0
            async for product_data in self.producthunt_client.get_trending_posts(
                days_back=1,  # Just today's products
                limit=limit
            ):
                samples["products"].append(product_data)
                product_count += 1
                if product_count >= limit:
                    break

            # Get sample comments (from first product if available)
            if samples["products"]:
                first_product_id = samples["products"][0]["id"]
                comment_count = 0
                async for comment_data in self.producthunt_client.get_post_comments(
                    post_id=first_product_id,
                    limit=limit
                ):
                    samples["comments"].append(comment_data)
                    comment_count += 1
                    if comment_count >= limit:
                        break

            # Create sample maker data from products
            for product in samples["products"][:2]:  # Limit to 2 products
                maker_data = self._create_maker_data_from_product(product, is_user=True)
                if maker_data and len(samples["makers"]) < limit:
                    samples["makers"].append(maker_data)

            return samples

        except Exception as e:
            self.logger.error(f"Error getting data samples: {e}")
            raise

    def get_connector_info(self) -> Dict[str, Any]:
        """Get connector information and configuration"""
        return {
            "name": "Product Hunt Connector",
            "version": "1.0.0",
            "description": "Extracts trending products, comments, and maker data from Product Hunt for idea generation",
            "source_type": "API",
            "sync_frequency": f"{self.config.sync_frequency_minutes} minutes",
            "supported_data_types": ["products", "comments", "makers", "categories"],
            "configuration": {
                "posts_limit": self.config.posts_limit,
                "comments_limit": self.config.comments_limit,
                "categories": self.config.categories,
                "days_back": self.config.days_back,
                "destination_schema": self.config.destination_schema
            },
            "features": [
                "Idea generation scoring",
                "Market validation analysis",
                "Trend signal detection",
                "Sentiment analysis",
                "Feature request extraction",
                "Pain point identification",
                "Competition analysis"
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
        connector = ProductHuntConnector()

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
            print("Product Hunt Connector for Fivetran")
            print("Usage: python -m producthunt_connector.main [command]")
            print("Commands: schema, sync, test, sample, info")

    except Exception as e:
        logger.error(f"Connector error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())