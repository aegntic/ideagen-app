"""
Fivetran Integration Pipelines for IdeaGen
Example data transformation and processing pipelines
"""

import asyncio
import logging
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Any, Optional
import json
from dataclasses import dataclass

from .reddit_connector.enhanced_reddit_connector import create_reddit_connector, RedditConfig
from .producthunt_connector.enhanced_producthunt_connector import create_producthunt_connector, ProductHuntConfig
from .trends_connector.enhanced_trends_connector import create_trends_connector, TrendsConfig
from .twitter_connector.enhanced_twitter_connector import create_twitter_connector, TwitterConfig


logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for integration pipelines"""
    sync_interval_minutes: int = 60
    batch_size: int = 1000
    retention_days: int = 90
    enable_real_time: bool = True
    enable_analytics: bool = True
    enable_alerts: bool = True


class IdeaGenPipelineManager:
    """
    Main pipeline manager for coordinating data collection and processing
    across all Fivetran connectors
    """

    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self.logger = logging.getLogger(__name__)
        self.connectors = {}
        self.metrics = {
            'total_records_processed': 0,
            'errors_count': 0,
            'last_sync': None,
            'pipeline_status': 'initialized'
        }

    async def initialize_connectors(self, connector_configs: Dict[str, Any]):
        """Initialize all connectors with their configurations"""
        try:
            # Initialize Reddit connector
            if 'reddit' in connector_configs:
                reddit_config = RedditConfig(**connector_configs['reddit'])
                self.connectors['reddit'] = create_reddit_connector(reddit_config)
                self.logger.info("Reddit connector initialized")

            # Initialize Product Hunt connector
            if 'producthunt' in connector_configs:
                ph_config = ProductHuntConfig(**connector_configs['producthunt'])
                self.connectors['producthunt'] = create_producthunt_connector(ph_config)
                self.logger.info("Product Hunt connector initialized")

            # Initialize Trends connector
            if 'trends' in connector_configs:
                trends_config = TrendsConfig(**connector_configs['trends'])
                self.connectors['trends'] = create_trends_connector(trends_config)
                self.logger.info("Google Trends connector initialized")

            # Initialize Twitter connector
            if 'twitter' in connector_configs:
                twitter_config = TwitterConfig(**connector_configs['twitter'])
                self.connectors['twitter'] = create_twitter_connector(twitter_config)
                self.logger.info("Twitter connector initialized")

            self.metrics['pipeline_status'] = 'connectors_ready'

        except Exception as e:
            self.logger.error(f"Failed to initialize connectors: {str(e)}")
            self.metrics['pipeline_status'] = 'initialization_failed'
            raise

    async def run_full_sync(self):
        """Run full synchronization across all connectors"""
        self.logger.info("Starting full sync across all connectors")
        self.metrics['pipeline_status'] = 'syncing'

        try:
            total_records = 0

            for platform, connector in self.connectors.items():
                try:
                    platform_records = await self._sync_connector(platform, connector)
                    total_records += platform_records
                    self.logger.info(f"Synced {platform_records} records from {platform}")

                except Exception as e:
                    self.logger.error(f"Failed to sync {platform}: {str(e)}")
                    self.metrics['errors_count'] += 1
                    continue

            self.metrics['total_records_processed'] = total_records
            self.metrics['last_sync'] = datetime.now(UTC).isoformat()
            self.metrics['pipeline_status'] = 'sync_complete'

            # Run post-sync analytics
            if self.config.enable_analytics:
                await self._run_post_sync_analytics()

            self.logger.info(f"Full sync completed: {total_records} total records processed")

        except Exception as e:
            self.logger.error(f"Full sync failed: {str(e)}")
            self.metrics['pipeline_status'] = 'sync_failed'
            raise

    async def _sync_connector(self, platform: str, connector) -> int:
        """Sync a single connector"""
        total_records = 0

        # Get tables for this connector
        tables = await connector.get_tables()

        for table in tables:
            try:
                # Extract data for this table
                records = await connector.extract_data(table.name)

                # Process and transform records
                processed_records = await self._process_records(platform, table.name, records)

                # Store records (in real implementation, this would use Fivetran)
                await self._store_records(table.name, processed_records)

                total_records += len(processed_records)

            except Exception as e:
                self.logger.error(f"Failed to sync table {table.name} from {platform}: {str(e)}")
                continue

        return total_records

    async def _process_records(self, platform: str, table_name: str, records: List) -> List:
        """Process and transform records"""
        processed = []

        for record in records:
            try:
                # Apply platform-specific transformations
                if platform == 'reddit':
                    processed_record = await self._process_reddit_record(record)
                elif platform == 'producthunt':
                    processed_record = await self._process_producthunt_record(record)
                elif platform == 'trends':
                    processed_record = await self._process_trends_record(record)
                elif platform == 'twitter':
                    processed_record = await self._process_twitter_record(record)
                else:
                    processed_record = record

                # Add processing metadata
                if hasattr(processed_record, 'data'):
                    processed_record.data['processed_at'] = datetime.now(UTC).isoformat()
                    processed_record.data['processing_pipeline'] = 'idegen_v1'

                processed.append(processed_record)

            except Exception as e:
                self.logger.error(f"Failed to process record {record.id}: {str(e)}")
                continue

        return processed

    async def _process_reddit_record(self, record) -> Any:
        """Process Reddit-specific records"""
        # Additional Reddit-specific processing
        data = record.data

        # Calculate engagement rate
        if 'score' in data and 'num_comments' in data:
            engagement = data['score'] + (data['num_comments'] * 2)
            data['engagement_score'] = engagement

        # Categorize post type
        title = data.get('title', '').lower()
        if any(keyword in title for keyword in ['looking for', 'any ideas', 'feedback']):
            data['post_category'] = 'idea_request'
        elif any(keyword in title for keyword in ['launched', 'created', 'built']):
            data['post_category'] = 'showcase'
        elif any(keyword in title for keyword in ['problem', 'issue', 'frustrated']):
            data['post_category'] = 'problem_statement'
        else:
            data['post_category'] = 'general'

        return record

    async def _process_producthunt_record(self, record) -> Any:
        """Process Product Hunt-specific records"""
        data = record.data

        # Calculate product maturity score
        votes = data.get('votes_count', 0)
        comments = data.get('comments_count', 0)
        makers = data.get('maker_count', 0)

        maturity_score = min((votes * 0.5 + comments * 2 + makers * 5) / 100, 100)
        data['product_maturity_score'] = maturity_score

        # Identify product type
        tags = []
        topics = data.get('topics', [])
        for topic in topics:
            if isinstance(topic, dict):
                tags.append(topic.get('name', '').lower())

        data['product_tags'] = tags
        data['product_type'] = self._classify_product_type(tags)

        return record

    async def _process_trends_record(self, record) -> Any:
        """Process Trends-specific records"""
        data = record.data

        # Calculate trend momentum
        if 'timeline' in data:
            timeline = data['timeline']
            if len(timeline) >= 2:
                recent_values = [entry.get('value', [0])[0] for entry in timeline[-7:]]
                older_values = [entry.get('value', [0])[0] for entry in timeline[-14:-7]]

                if older_values:
                    momentum = (sum(recent_values) - sum(older_values)) / len(older_values)
                    data['trend_momentum'] = round(momentum, 2)

        return record

    async def _process_twitter_record(self, record) -> Any:
        """Process Twitter-specific records"""
        data = record.data

        # Calculate influence-weighted engagement
        public_metrics = data.get('public_metrics', {})
        likes = public_metrics.get('like_count', 0)
        retweets = public_metrics.get('retweet_count', 0)
        replies = public_metrics.get('reply_count', 0)

        # Weight retweets more heavily
        weighted_engagement = likes + (retweets * 3) + (replies * 2)
        data['weighted_engagement'] = weighted_engagement

        # Identify conversation type
        text = data.get('text', '').lower()
        if any(keyword in text for keyword in ['building', 'launched', 'created']):
            data['conversation_type'] = 'product_announcement'
        elif any(keyword in text for keyword in ['need', 'looking for', 'help']):
            data['conversation_type'] = 'request'
        elif any(keyword in text for keyword in ['love', 'amazing', 'great']):
            data['conversation_type'] = 'positive_feedback'
        else:
            data['conversation_type'] = 'general'

        return record

    def _classify_product_type(self, tags: List[str]) -> str:
        """Classify product type based on tags"""
        if any(tag in tags for tag in ['saas', 'software', 'web app']):
            return 'saas'
        elif any(tag in tags for tag in ['mobile', 'ios', 'android']):
            return 'mobile_app'
        elif any(tag in tags for tag in ['api', 'developer', 'tool']):
            return 'developer_tool'
        elif any(tag in tags for tag in ['design', 'ui', 'ux']):
            return 'design_tool'
        else:
            return 'other'

    async def _store_records(self, table_name: str, records: List):
        """Store records (mock implementation)"""
        # In real implementation, this would use Fivetran to sync to destination
        self.logger.debug(f"Storing {len(records)} records for table {table_name}")
        # Mock: just count records
        return len(records)

    async def _run_post_sync_analytics(self):
        """Run analytics after sync completion"""
        self.logger.info("Running post-sync analytics")

        # Example analytics queries
        analytics_queries = [
            "Top trending keywords across platforms",
            "High-potential ideas identified",
            "User pain points and problems",
            "Market opportunities by category",
            "Competitive landscape analysis"
        ]

        for query in analytics_queries:
            try:
                # Mock analytics processing
                self.logger.info(f"Processing analytics: {query}")
                await asyncio.sleep(0.1)  # Simulate processing time

            except Exception as e:
                self.logger.error(f"Failed to process analytics query '{query}': {str(e)}")

    async def start_continuous_sync(self):
        """Start continuous synchronization"""
        self.logger.info(f"Starting continuous sync with {self.config.sync_interval_minutes} minute intervals")

        while True:
            try:
                await self.run_full_sync()

                # Wait for next sync
                await asyncio.sleep(self.config.sync_interval_minutes * 60)

            except KeyboardInterrupt:
                self.logger.info("Continuous sync stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Continuous sync error: {str(e)}")
                # Wait before retrying
                await asyncio.sleep(60)

    async def get_pipeline_health(self) -> Dict[str, Any]:
        """Get overall pipeline health status"""
        health = {
            'status': self.metrics['pipeline_status'],
            'last_sync': self.metrics['last_sync'],
            'total_records_processed': self.metrics['total_records_processed'],
            'errors_count': self.metrics['errors_count'],
            'connectors_count': len(self.connectors),
            'connector_health': {},
            'timestamp': datetime.now(UTC).isoformat()
        }

        # Check individual connector health
        for platform, connector in self.connectors.items():
            try:
                connector_health = await connector.health_check()
                health['connector_health'][platform] = connector_health

            except Exception as e:
                health['connector_health'][platform] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }

        return health

    async def cleanup(self):
        """Cleanup all connectors"""
        for platform, connector in self.connectors.items():
            try:
                await connector.cleanup()
                self.logger.info(f"Cleaned up {platform} connector")

            except Exception as e:
                self.logger.error(f"Failed to cleanup {platform} connector: {str(e)}")


class RealTimeProcessor:
    """Real-time data processing for immediate insights"""

    def __init__(self, pipeline_manager: IdeaGenPipelineManager):
        self.pipeline_manager = pipeline_manager
        self.logger = logging.getLogger(__name__)
        self.alert_thresholds = {
            'high_engagement': 1000,
            'viral_trend': 10000,
            'market_opportunity': 80
        }

    async def process_real_time_data(self, platform: str, records: List):
        """Process incoming real-time data"""
        for record in records:
            await self._analyze_record_for_alerts(platform, record)

    async def _analyze_record_for_alerts(self, platform: str, record):
        """Analyze individual record for alert conditions"""
        data = record.data

        # Check for high engagement
        if platform == 'reddit' and data.get('score', 0) > self.alert_thresholds['high_engagement']:
            await self._send_alert('high_engagement', {
                'platform': platform,
                'title': data.get('title'),
                'score': data.get('score'),
                'url': data.get('permalink')
            })

        elif platform == 'producthunt' and data.get('votes_count', 0) > self.alert_thresholds['high_engagement']:
            await self._send_alert('high_engagement', {
                'platform': platform,
                'product': data.get('name'),
                'votes': data.get('votes_count'),
                'url': data.get('url')
            })

        # Check for market opportunities
        idea_potential = data.get('idea_potential_score', 0)
        if idea_potential > self.alert_thresholds['market_opportunity']:
            await self._send_alert('market_opportunity', {
                'platform': platform,
                'potential_score': idea_potential,
                'title': data.get('title') or data.get('name'),
                'description': data.get('description') or data.get('tagline')
            })

    async def _send_alert(self, alert_type: str, data: Dict[str, Any]):
        """Send alert for significant events"""
        self.logger.info(f"ALERT - {alert_type}: {json.dumps(data, indent=2)}")

        # In real implementation, this would send to notification system
        # email, Slack, webhook, etc.


# Example usage and configuration
async def main():
    """Example pipeline execution"""
    logging.basicConfig(level=logging.INFO)

    # Pipeline configuration
    pipeline_config = PipelineConfig(
        sync_interval_minutes=30,
        batch_size=500,
        enable_real_time=True,
        enable_analytics=True
    )

    # Connector configurations (use environment variables in production)
    connector_configs = {
        'reddit': {
            'client_id': 'your_reddit_client_id',
            'client_secret': 'your_reddit_client_secret',
            'subreddits': ['entrepreneur', 'startups', 'SaaS', 'SideProject'],
            'min_upvotes': 10
        },
        'producthunt': {
            'api_token': 'your_producthunt_token',
            'days_back': 7,
            'min_votes': 5
        },
        'trends': {
            'keywords': ['startup ideas', 'saas', 'productivity tools'],
            'geo': 'US'
        },
        'twitter': {
            'bearer_token': 'your_twitter_bearer_token',
            'keywords': ['startup idea', 'saas', 'build in public'],
            'min_likes': 10
        }
    }

    # Initialize and run pipeline
    pipeline_manager = IdeaGenPipelineManager(pipeline_config)

    try:
        # Initialize connectors
        await pipeline_manager.initialize_connectors(connector_configs)

        # Run initial sync
        await pipeline_manager.run_full_sync()

        # Get pipeline health
        health = await pipeline_manager.get_pipeline_health()
        print(f"Pipeline health: {json.dumps(health, indent=2, default=str)}")

        # Start continuous sync (commented out for demo)
        # await pipeline_manager.start_continuous_sync()

    except Exception as e:
        logger.error(f"Pipeline execution failed: {str(e)}")

    finally:
        # Cleanup
        await pipeline_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())