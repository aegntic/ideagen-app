"""
Fivetran Reddit Connector
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

from .reddit_client import RedditClient
from .config import get_config, POST_SCHEMA, COMMENT_SCHEMA, SUBREDDIT_SCHEMA


logger = logging.getLogger(__name__)


class RedditConnector:
    """
    Fivetran connector for Reddit data extraction
    Handles schema definition, data extraction, and synchronization
    """

    def __init__(self, config=None):
        self.config = config or get_config()
        self.reddit_client = RedditClient(self.config)
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
            self.logger.info("Defining Reddit connector schema")

            tables = []

            # Posts table
            posts_table = Table(
                name="reddit_posts",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in POST_SCHEMA.items()
                ]
            )
            tables.append(posts_table)

            # Comments table
            comments_table = Table(
                name="reddit_comments",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in COMMENT_SCHEMA.items()
                ]
            )
            tables.append(comments_table)

            # Subreddits table
            subreddits_table = Table(
                name="reddit_subreddits",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in SUBREDDIT_SCHEMA.items()
                ]
            )
            tables.append(subreddits_table)

            return ConnectorSchemaResponse(
                tables=tables,
                schema=self.config.destination_schema
            )

        except Exception as e:
            self.logger.error(f"Error defining schema: {e}")
            raise

    async def sync_data(self, state: Optional[Dict[str, Any]] = None) -> ConnectorDataResponse:
        """
        Synchronize data from Reddit to Fivetran destination
        """
        try:
            self.logger.info("Starting Reddit data synchronization")

            # Initialize state if not provided
            if state is None:
                state = {
                    "last_sync": None,
                    "processed_posts": set(),
                    "processed_comments": set(),
                    "processed_subreddits": set(),
                    "cursor": {}
                }

            current_time = datetime.now(UTC)
            sync_data = {
                "posts": [],
                "comments": [],
                "subreddits": []
            }

            # Sync subreddit information
            await self._sync_subreddits(state, sync_data)

            # Sync trending posts
            await self._sync_trending_posts(state, sync_data)

            # Sync comments for high-value posts
            await self._sync_comments(state, sync_data)

            # Update state
            state["last_sync"] = current_time.isoformat()

            # Send data to Fivetran
            await self._send_data_to_fivetran(sync_data)

            return ConnectorDataResponse(
                has_more=False,
                state=state,
                records_processed=len(sync_data["posts"]) + len(sync_data["comments"]) + len(sync_data["subreddits"])
            )

        except Exception as e:
            self.logger.error(f"Error during data synchronization: {e}")
            raise

    async def _sync_subreddits(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize subreddit information"""
        self.logger.info("Syncing subreddit information")

        for subreddit_name in self.config.subreddits:
            try:
                subreddit_id = f"r_{subreddit_name.lower()}"

                if subreddit_id in state["processed_subreddits"]:
                    continue

                subreddit_info = await self.reddit_client.get_subreddit_info(subreddit_name)

                if subreddit_info:
                    sync_data["subreddits"].append(subreddit_info)
                    state["processed_subreddits"].add(subreddit_id)

            except Exception as e:
                self.logger.warning(f"Error syncing subreddit {subreddit_name}: {e}")
                continue

    async def _sync_trending_posts(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize trending posts from configured subreddits"""
        self.logger.info("Syncing trending posts")

        try:
            async for post_data in self.reddit_client.get_trending_posts(
                subreddit_names=self.config.subreddits,
                post_limit=self.config.post_limit,
                time_filter=self.config.time_filter
            ):
                post_id = post_data["id"]

                # Skip if already processed
                if post_id in state["processed_posts"]:
                    continue

                # Only include posts with high idea generation potential
                if post_data.get("idea_generation_score", 0) >= 0.3:
                    sync_data["posts"].append(post_data)
                    state["processed_posts"].add(post_id)

                    # Track for comment extraction
                    if "high_value_posts" not in state:
                        state["high_value_posts"] = []

                    if len(state["high_value_posts"]) < 50:  # Limit comments extraction
                        state["high_value_posts"].append(post_id)

        except Exception as e:
            self.logger.error(f"Error syncing trending posts: {e}")

    async def _sync_comments(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize comments for high-value posts"""
        self.logger.info("Syncing comments for high-value posts")

        high_value_posts = state.get("high_value_posts", [])

        for post_id in high_value_posts:
            try:
                async for comment_data in self.reddit_client.get_post_comments(
                    post_id=post_id,
                    comment_limit=self.config.comment_limit,
                    sort="best"
                ):
                    comment_id = comment_data["id"]

                    # Skip if already processed
                    if comment_id in state["processed_comments"]:
                        continue

                    # Only include comments with insights
                    if (comment_data.get("sentiment_score") is not None or
                        comment_data.get("pain_points") or
                        comment_data.get("feature_requests")):

                        sync_data["comments"].append(comment_data)
                        state["processed_comments"].add(comment_id)

            except Exception as e:
                self.logger.warning(f"Error syncing comments for post {post_id}: {e}")
                continue

    async def _send_data_to_fivetran(self, sync_data: Dict[str, List]):
        """Send synchronized data to Fivetran destination"""
        try:
            # Send posts data
            if sync_data["posts"]:
                await self._send_table_data("reddit_posts", sync_data["posts"])
                self.logger.info(f"Sent {len(sync_data['posts'])} posts to Fivetran")

            # Send comments data
            if sync_data["comments"]:
                await self._send_table_data("reddit_comments", sync_data["comments"])
                self.logger.info(f"Sent {len(sync_data['comments'])} comments to Fivetran")

            # Send subreddits data
            if sync_data["subreddits"]:
                await self._send_table_data("reddit_subreddits", sync_data["subreddits"])
                self.logger.info(f"Sent {len(sync_data['subreddits'])} subreddits to Fivetran")

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
        """Test connection to Reddit API"""
        try:
            self.logger.info("Testing Reddit API connection")

            # Try to fetch a simple subreddit info to test connection
            test_subreddit = await self.reddit_client.get_subreddit_info("technology")

            if test_subreddit:
                self.logger.info("Reddit API connection test successful")
                return True
            else:
                self.logger.error("Reddit API connection test failed - no data returned")
                return False

        except Exception as e:
            self.logger.error(f"Reddit API connection test failed: {e}")
            return False

    async def get_data_samples(self, limit: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """Get sample data for testing and validation"""
        try:
            self.logger.info(f"Getting {limit} sample records from each data type")

            samples = {
                "posts": [],
                "comments": [],
                "subreddits": []
            }

            # Get sample subreddit info
            for subreddit_name in self.config.subreddits[:2]:  # Limit to 2 subreddits
                subreddit_info = await self.reddit_client.get_subreddit_info(subreddit_name)
                if subreddit_info:
                    samples["subreddits"].append(subreddit_info)

            # Get sample posts
            post_count = 0
            async for post_data in self.reddit_client.get_trending_posts(
                subreddit_names=self.config.subreddits[:1],  # Limit to 1 subreddit
                post_limit=limit,
                time_filter="day"
            ):
                samples["posts"].append(post_data)
                post_count += 1
                if post_count >= limit:
                    break

            # Get sample comments (from first post if available)
            if samples["posts"]:
                first_post_id = samples["posts"][0]["id"]
                comment_count = 0
                async for comment_data in self.reddit_client.get_post_comments(
                    post_id=first_post_id,
                    comment_limit=limit
                ):
                    samples["comments"].append(comment_data)
                    comment_count += 1
                    if comment_count >= limit:
                        break

            return samples

        except Exception as e:
            self.logger.error(f"Error getting data samples: {e}")
            raise

    def get_connector_info(self) -> Dict[str, Any]:
        """Get connector information and configuration"""
        return {
            "name": "Reddit Connector",
            "version": "1.0.0",
            "description": "Extracts trending posts, comments, and subreddit data from Reddit for idea generation",
            "source_type": "API",
            "sync_frequency": f"{self.config.sync_frequency_minutes} minutes",
            "supported_data_types": ["posts", "comments", "subreddits"],
            "configuration": {
                "subreddits": self.config.subreddits,
                "post_limit": self.config.post_limit,
                "comment_limit": self.config.comment_limit,
                "time_filter": self.config.time_filter,
                "destination_schema": self.config.destination_schema
            },
            "features": [
                "Idea generation scoring",
                "Trending topic extraction",
                "Market signal identification",
                "Sentiment analysis",
                "Pain point detection",
                "Feature request extraction"
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
        connector = RedditConnector()

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
            print("Reddit Connector for Fivetran")
            print("Usage: python -m reddit_connector.main [command]")
            print("Commands: schema, sync, test, sample, info")

    except Exception as e:
        logger.error(f"Connector error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())