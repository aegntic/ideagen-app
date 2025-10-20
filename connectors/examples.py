"""
Fivetran Connector Examples for IdeaGen
Practical examples demonstrating connector usage and integration patterns
"""

import asyncio
import logging
import os
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Any

from .integration_pipelines import IdeaGenPipelineManager, PipelineConfig, RealTimeProcessor
from .base_connector import DataTransformer


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IdeaGenConnectorExamples:
    """Examples demonstrating practical usage of IdeaGen Fivetran connectors"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def example_1_basic_data_extraction(self):
        """Example 1: Basic data extraction from all platforms"""
        self.logger.info("=== Example 1: Basic Data Extraction ===")

        # Initialize pipeline manager
        pipeline_config = PipelineConfig(
            sync_interval_minutes=60,
            batch_size=100,
            enable_analytics=True
        )

        pipeline_manager = IdeaGenPipelineManager(pipeline_config)

        # Example configurations (use environment variables in production)
        connector_configs = {
            'reddit': {
                'client_id': os.getenv('REDDIT_CLIENT_ID', 'demo_id'),
                'client_secret': os.getenv('REDDIT_CLIENT_SECRET', 'demo_secret'),
                'subreddits': ['entrepreneur', 'startups', 'SaaS', 'SideProject'],
                'min_upvotes': 10,
                'include_comments': True
            },
            'producthunt': {
                'api_token': os.getenv('PRODUCTHUNT_TOKEN', 'demo_token'),
                'days_back': 7,
                'min_votes': 5,
                'categories': ['productivity', 'developer-tools']
            },
            'trends': {
                'keywords': ['startup ideas', 'saas', 'productivity tools', 'AI automation'],
                'geo': 'US',
                'time_range': 'today 7-d',
                'min_interest_level': 20
            },
            'twitter': {
                'bearer_token': os.getenv('TWITTER_BEARER_TOKEN', 'demo_token'),
                'keywords': ['startup idea', 'saas', 'build in public', 'no-code'],
                'hashtags': ['#startup', '#saas', '#buildinpublic'],
                'min_likes': 10,
                'exclude_replies': True
            }
        }

        try:
            # Initialize connectors
            await pipeline_manager.initialize_connectors(connector_configs)

            # Run sync for a specific table
            reddit_connector = pipeline_manager.connectors.get('reddit')
            if reddit_connector:
                # Extract recent Reddit posts
                posts = await reddit_connector.extract_data('reddit_posts')
                print(f"Extracted {len(posts)} Reddit posts")

                # Show example of processed data
                if posts:
                    example_post = posts[0]
                    print(f"Example post: {example_post.data.get('title')}")
                    print(f"Idea signals: {example_post.data.get('idea_signals', {})}")
                    print(f"Engagement score: {example_post.data.get('engagement_score', 0)}")

            # Extract Product Hunt data
            ph_connector = pipeline_manager.connectors.get('producthunt')
            if ph_connector:
                products = await ph_connector.extract_data('producthunt_products')
                print(f"Extracted {len(products)} Product Hunt products")

                if products:
                    example_product = products[0]
                    print(f"Example product: {example_product.data.get('name')}")
                    print(f"Market signals: {example_product.data.get('market_signals', {})}")

            # Extract trending topics
            trends_connector = pipeline_manager.connectors.get('trends')
            if trends_connector:
                trending = await trends_connector.extract_data('trending_searches')
                print(f"Extracted {len(trending)} trending searches")

                if trending:
                    example_trend = trending[0]
                    print(f"Example trend: {example_trend.data.get('title')}")
                    print(f"Business opportunity: {example_trend.data.get('business_opportunity', {})}")

            # Get pipeline health
            health = await pipeline_manager.get_pipeline_health()
            print(f"Pipeline health: {health['status']}")
            print(f"Total records processed: {health['total_records_processed']}")

        except Exception as e:
            self.logger.error(f"Example 1 failed: {str(e)}")

        finally:
            await pipeline_manager.cleanup()

    async def example_2_idea_discovery_pipeline(self):
        """Example 2: Automated idea discovery and validation pipeline"""
        self.logger.info("=== Example 2: Idea Discovery Pipeline ===")

        # Create focused configuration for idea discovery
        pipeline_config = PipelineConfig(
            sync_interval_minutes=15,  # More frequent for idea discovery
            batch_size=200,
            enable_real_time=True,
            enable_analytics=True,
            enable_alerts=True
        )

        pipeline_manager = IdeaGenPipelineManager(pipeline_config)

        # Configure for idea discovery
        connector_configs = {
            'reddit': {
                'client_id': os.getenv('REDDIT_CLIENT_ID', 'demo_id'),
                'client_secret': os.getenv('REDDIT_CLIENT_SECRET', 'demo_secret'),
                'subreddits': ['SideProject', 'SaaS', 'microsaas', 'IndieHackers'],
                'keywords': ['problem', 'frustrated', 'looking for', 'need tool'],
                'min_upvotes': 5,  # Lower threshold to catch emerging ideas
                'include_comments': True
            },
            'producthunt': {
                'api_token': os.getenv('PRODUCTHUNT_TOKEN', 'demo_token'),
                'days_back': 3,  # Recent products only
                'min_votes': 3,  # Include early-stage products
                'categories': ['productivity', 'developer-tools', 'no-code']
            },
            'twitter': {
                'bearer_token': os.getenv('TWITTER_BEARER_TOKEN', 'demo_token'),
                'keywords': ['wish there was', 'someone should build', 'problem with', 'need tool'],
                'hashtags': ['#buildinpublic', '#sideproject', '#wtf'],
                'min_likes': 5,
                'exclude_replies': False  # Include replies to catch problems
            }
        }

        try:
            await pipeline_manager.initialize_connectors(connector_configs)

            # Run focused sync
            await pipeline_manager.run_full_sync()

            # Simulate idea discovery analysis
            discovered_ideas = await self._analyze_discovered_ideas(pipeline_manager)

            print(f"Discovered {len(discovered_ideas)} high-potential ideas:")
            for i, idea in enumerate(discovered_ideas[:5], 1):
                print(f"{i}. {idea['title']} (Score: {idea['score']})")
                print(f"   Source: {idea['source']}")
                print(f"   Problem: {idea['problem']}")
                print(f"   Market: {idea['market_opportunity']}")
                print()

        except Exception as e:
            self.logger.error(f"Example 2 failed: {str(e)}")

        finally:
            await pipeline_manager.cleanup()

    async def example_3_market_intelligence_dashboard(self):
        """Example 3: Market intelligence and competitive analysis"""
        self.logger.info("=== Example 3: Market Intelligence Dashboard ===")

        pipeline_config = PipelineConfig(
            sync_interval_minutes=30,
            batch_size=500,
            enable_analytics=True
        )

        pipeline_manager = IdeaGenPipelineManager(pipeline_config)

        # Configure for market intelligence
        connector_configs = {
            'reddit': {
                'client_id': os.getenv('REDDIT_CLIENT_ID', 'demo_id'),
                'client_secret': os.getenv('REDDIT_CLIENT_SECRET', 'demo_secret'),
                'subreddits': ['SaaS', 'startups', 'Entrepreneur', 'Marketing'],
                'keywords': ['competitor', 'alternative', 'vs', 'comparison'],
                'min_upvotes': 20
            },
            'producthunt': {
                'api_token': os.getenv('PRODUCTHUNT_TOKEN', 'demo_token'),
                'days_back': 14,
                'categories': ['productivity', 'marketing', 'analytics'],
                'min_votes': 50
            },
            'trends': {
                'keywords': [
                    'project management software', 'crm software', 'email marketing',
                    'analytics tools', 'collaboration tools', 'automation software'
                ],
                'geo': 'US',
                'time_range': 'today 30-d'
            },
            'twitter': {
                'bearer_token': os.getenv('TWITTER_BEARER_TOKEN', 'demo_token'),
                'keywords': ['vs', 'alternative', 'competitor', 'comparison'],
                'hashtags': ['#saas', '#startuptools', '#marketing'],
                'min_likes': 50
            }
        }

        try:
            await pipeline_manager.initialize_connectors(connector_configs)
            await pipeline_manager.run_full_sync()

            # Generate market intelligence report
            market_report = await self._generate_market_intelligence_report(pipeline_manager)

            print("=== Market Intelligence Report ===")
            print(f"Report generated: {datetime.now(UTC).isoformat()}")
            print()

            print("🔥 Trending Keywords:")
            for keyword in market_report['trending_keywords'][:5]:
                print(f"   • {keyword['keyword']} (Platforms: {', '.join(keyword['platforms'])})")

            print("\n💡 High-Potential Opportunities:")
            for opportunity in market_report['opportunities'][:3]:
                print(f"   • {opportunity['name']}")
                print(f"     Score: {opportunity['score']}/100")
                print(f"     Market: {opportunity['market_validation']}")

            print("\n⚠️  Identified Problems:")
            for problem in market_report['problems'][:3]:
                print(f"   • {problem['title']}")
                print(f"     Frequency: {problem['mentions']} mentions")
                print(f"     Platforms: {', '.join(problem['platforms'])}")

            print("\n📊 Platform Insights:")
            for platform, insights in market_report['platform_insights'].items():
                print(f"   {platform.capitalize()}: {insights['total_records']} records, "
                      f"avg engagement: {insights['avg_engagement']:.1f}")

        except Exception as e:
            self.logger.error(f"Example 3 failed: {str(e)}")

        finally:
            await pipeline_manager.cleanup()

    async def example_4_real_time_monitoring(self):
        """Example 4: Real-time monitoring and alerting"""
        self.logger.info("=== Example 4: Real-time Monitoring ===")

        pipeline_config = PipelineConfig(
            sync_interval_minutes=5,  # Very frequent for real-time
            batch_size=50,
            enable_real_time=True,
            enable_alerts=True
        )

        pipeline_manager = IdeaGenPipelineManager(pipeline_config)
        real_time_processor = RealTimeProcessor(pipeline_manager)

        # Configure for real-time monitoring
        connector_configs = {
            'reddit': {
                'client_id': os.getenv('REDDIT_CLIENT_ID', 'demo_id'),
                'client_secret': os.getenv('REDDIT_CLIENT_SECRET', 'demo_secret'),
                'subreddits': ['programming', 'startups', 'Entrepreneur'],
                'post_types': ['hot', 'rising'],  # Focus on rising content
                'min_upvotes': 5
            },
            'twitter': {
                'bearer_token': os.getenv('TWITTER_BEARER_TOKEN', 'demo_token'),
                'keywords': ['launching', 'just launched', 'beta release'],
                'hashtags': ['#launch', '#startup', '#beta'],
                'min_likes': 10
            }
        }

        try:
            await pipeline_manager.initialize_connectors(connector_configs)

            # Simulate real-time monitoring
            for i in range(3):  # Simulate 3 monitoring cycles
                print(f"\n--- Monitoring Cycle {i+1} ---")

                # Extract recent data
                for platform, connector in pipeline_manager.connectors.items():
                    records = await connector.extract_data(f'{platform}_posts' if platform == 'reddit' else 'twitter_tweets')

                    if records:
                        # Process for real-time alerts
                        await real_time_processor.process_real_time_data(platform, records)

                        print(f"📡 {platform.capitalize()}: Processed {len(records)} new records")

                        # Show any significant findings
                        significant_records = [
                            r for r in records
                            if r.data.get('engagement_score', 0) > 100
                            or r.data.get('idea_potential_score', 0) > 70
                        ]

                        if significant_records:
                            print(f"🚨 Found {len(significant_records)} significant items on {platform}")
                            for record in significant_records[:2]:
                                title = record.data.get('title') or record.data.get('text', '')[:50]
                                print(f"   • {title}...")

                # Wait between cycles
                await asyncio.sleep(2)

        except Exception as e:
            self.logger.error(f"Example 4 failed: {str(e)}")

        finally:
            await pipeline_manager.cleanup()

    async def _analyze_discovered_ideas(self, pipeline_manager) -> List[Dict[str, Any]]:
        """Analyze discovered ideas and rank by potential"""
        # Mock implementation - in reality, this would query the database
        discovered_ideas = [
            {
                'title': 'AI-powered customer service automation',
                'score': 85,
                'source': 'reddit',
                'problem': 'Businesses struggling with customer service efficiency',
                'market_opportunity': 'Large - growing demand for AI solutions',
                'validation_signals': ['High engagement', 'Multiple mentions', 'Clear problem statement']
            },
            {
                'title': 'No-code workflow builder for SMBs',
                'score': 78,
                'source': 'producthunt',
                'problem': 'Small businesses need automation without technical skills',
                'market_opportunity': 'Medium - existing competitors but room for innovation',
                'validation_signals': ['Recent product launch', 'Good early traction', 'Clear target market']
            },
            {
                'title': 'Remote team collaboration hub',
                'score': 72,
                'source': 'twitter',
                'problem': 'Distributed teams struggle with effective collaboration',
                'market_opportunity': 'High - growing remote work trend',
                'validation_signals': ['Viral discussion', 'Multiple user requests', 'Influencer mentions']
            }
        ]

        return sorted(discovered_ideas, key=lambda x: x['score'], reverse=True)

    async def _generate_market_intelligence_report(self, pipeline_manager) -> Dict[str, Any]:
        """Generate comprehensive market intelligence report"""
        # Mock implementation - in reality, this would aggregate database queries
        return {
            'trending_keywords': [
                {'keyword': 'AI automation', 'platforms': ['reddit', 'twitter', 'trends']},
                {'keyword': 'no-code tools', 'platforms': ['producthunt', 'twitter']},
                {'keyword': 'remote work', 'platforms': ['trends', 'twitter']},
                {'keyword': 'productivity software', 'platforms': ['reddit', 'producthunt']}
            ],
            'opportunities': [
                {'name': 'AI-powered productivity tools', 'score': 88, 'market_validation': 'high'},
                {'name': 'No-code business automation', 'score': 82, 'market_validation': 'medium'},
                {'name': 'Remote team collaboration', 'score': 76, 'market_validation': 'high'}
            ],
            'problems': [
                {'title': 'Inefficient customer service processes', 'mentions': 45, 'platforms': ['reddit', 'twitter']},
                {'title': 'Complex workflow automation', 'mentions': 32, 'platforms': ['reddit', 'producthunt']},
                {'title': 'Poor remote team communication', 'mentions': 28, 'platforms': ['twitter', 'reddit']}
            ],
            'platform_insights': {
                'reddit': {'total_records': 1250, 'avg_engagement': 45.2},
                'producthunt': {'total_records': 89, 'avg_engagement': 234.7},
                'trends': {'total_records': 156, 'avg_engagement': 67.3},
                'twitter': {'total_records': 2100, 'avg_engagement': 12.8}
            }
        }


async def run_all_examples():
    """Run all examples"""
    examples = IdeaGenConnectorExamples()

    print("🚀 Starting Fivetran Connector Examples for IdeaGen\n")

    try:
        # Example 1: Basic data extraction
        await examples.example_1_basic_data_extraction()
        await asyncio.sleep(2)

        # Example 2: Idea discovery pipeline
        await examples.example_2_idea_discovery_pipeline()
        await asyncio.sleep(2)

        # Example 3: Market intelligence
        await examples.example_3_market_intelligence_dashboard()
        await asyncio.sleep(2)

        # Example 4: Real-time monitoring
        await examples.example_4_real_time_monitoring()

        print("\n✅ All examples completed successfully!")

    except Exception as e:
        logger.error(f"Example execution failed: {str(e)}")


if __name__ == "__main__":
    # Set up environment variables for demo
    os.environ.setdefault('REDDIT_CLIENT_ID', 'demo_client_id')
    os.environ.setdefault('REDDIT_CLIENT_SECRET', 'demo_client_secret')
    os.environ.setdefault('PRODUCTHUNT_TOKEN', 'demo_token')
    os.environ.setdefault('TWITTER_BEARER_TOKEN', 'demo_bearer_token')

    # Run examples
    asyncio.run(run_all_examples())