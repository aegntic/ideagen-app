# Fivetran Connectors for IdeaGen

Production-ready Fivetran connectors designed specifically for the IdeaGen application to automate data ingestion from multiple social platforms and trend sources.

## Overview

This connector suite enables IdeaGen to automatically collect and process data from:
- **Reddit** - Trending posts, comments, and subreddit activity
- **Product Hunt** - New products, makers, reviews, and market signals
- **Google Trends** - Trending topics, related queries, and regional interest
- **Twitter/X** - Tweets, trending topics, conversations, and user insights

## Architecture

### Base Connector (`base-connector.py`)

All connectors inherit from the `BaseConnector` class which provides:

- **Shared Functionality**: Common authentication, rate limiting, error handling
- **Data Transformation**: Standardized data cleaning and entity extraction
- **Fivetran Integration**: SDK integration with schema definition and data extraction
- **Production Features**: Retry logic, health checks, configuration validation

### Core Features

- **Automatic Entity Extraction**: Identifies companies, technologies, keywords, and concepts
- **Sentiment Analysis**: Determines emotional tone and user sentiment
- **Idea Signal Detection**: Identifies business opportunities and pain points
- **Market Intelligence**: Provides competitive analysis and market insights
- **Real-time Processing**: Continuously syncs data with configurable intervals
- **Scalable Architecture**: Handles high-volume data with efficient batching

## Connectors

### 1. Reddit Connector (`reddit_connector/`)

**Purpose**: Extract trending discussions, product feedback, and user problems from Reddit communities.

**Key Features**:
- Multi-subreddit monitoring
- Comment thread analysis
- Entity and keyword extraction
- Idea signal detection
- Pain point identification

**Data Sources**:
- Posts from configured subreddits
- Comments and replies
- Subreddit metadata
- User engagement metrics

**Configuration**:
```python
RedditConfig(
    client_id="your_reddit_client_id",
    client_secret="your_reddit_client_secret",
    subreddits=["entrepreneur", "startups", "SaaS", "SideProject"],
    post_types=["hot", "top"],
    include_comments=True,
    min_upvotes=10
)
```

**Tables Created**:
- `reddit_posts` - Main post data with extracted entities
- `reddit_comments` - Comment analysis and sentiment
- `reddit_subreddits` - Community metadata and statistics

### 2. Product Hunt Connector (`producthunt_connector/`)

**Purpose**: Monitor new product launches, maker activity, and market trends.

**Key Features**:
- Real-time product discovery
- Maker and investor tracking
- Review sentiment analysis
- Market opportunity assessment
- Competitive intelligence

**Data Sources**:
- Daily product launches
- Maker profiles and histories
- User reviews and comments
- Product categories and topics

**Configuration**:
```python
ProductHuntConfig(
    api_token="your_producthunt_api_token",
    categories=["productivity", "developer-tools", "saas"],
    days_back=7,
    include_comments=True,
    min_votes=5
)
```

**Tables Created**:
- `producthunt_products` - Product data with market signals
- `producthunt_makers` - Maker profiles and influence scores
- `producthunt_comments` - User feedback and sentiment
- `producthunt_topics` - Category trends and statistics

### 3. Google Trends Connector (`trends_connector/`)

**Purpose**: Track trending topics, search patterns, and regional interest.

**Key Features**:
- Trending topic discovery
- Regional interest analysis
- Related query tracking
- Growth rate calculation
- Seasonal pattern detection

**Data Sources**:
- Daily trending searches
- Interest over time data
- Related queries and topics
- Regional search patterns

**Configuration**:
```python
TrendsConfig(
    geo="US",
    time_range="today 30-d",
    keywords=["startup ideas", "saas", "productivity tools"],
    categories=[0, 7, 312],  # All, Business, Computer & Electronics
    min_interest_level=20
)
```

**Tables Created**:
- `trending_searches` - Daily trending topics with business opportunities
- `interest_over_time` - Historical interest data for keywords
- `related_queries` - Associated search terms and relationships
- `regional_interest` - Geographic distribution of interest
- `trend_analysis` - Comprehensive trend analytics and insights

### 4. Twitter/X Connector (`twitter_connector/`)

**Purpose**: Monitor real-time conversations, trending topics, and user sentiment.

**Key Features**:
- Real-time tweet monitoring
- Hashtag and mention tracking
- Conversation thread analysis
- Influencer identification
- Sentiment and opinion mining

**Data Sources**:
- Tweets based on keywords and hashtags
- User profiles and influence metrics
- Trending topics and conversations
- Reply chains and discussions

**Configuration**:
```python
TwitterConfig(
    bearer_token="your_twitter_bearer_token",
    keywords=["startup idea", "saas", "build in public"],
    hashtags=["#startup", "#saas", "#buildinpublic"],
    exclude_replies=True,
    min_likes=10,
    languages=["en"]
)
```

**Tables Created**:
- `twitter_tweets` - Tweet data with extracted entities and sentiment
- `twitter_users` - User profiles with influence scores
- `twitter_trending_topics` - Trending hashtags and topics
- `twitter_hashtags` - Hashtag performance metrics
- `twitter_conversations` - Conversation thread analysis

## Installation and Setup

### Prerequisites

1. **Python 3.8+** with required packages:
   ```bash
   pip install aiohttp pandas dataclasses
   ```

2. **Fivetran Account** with connector access

3. **API Credentials** for each platform:
   - Reddit: Client ID and Secret
   - Product Hunt: API Token
   - Twitter/X: Bearer Token
   - Google Trends: No authentication required

4. **PostgreSQL Database** with extended schema

### Database Setup

1. Run the schema extensions:
   ```sql
   \i database/fivetran_extensions.sql
   ```

2. Verify tables are created:
   ```sql
   \dt reddit_*
   \dt producthunt_*
   \dt trending_*
   \dt twitter_*
   ```

### Configuration

Create environment variables for sensitive credentials:

```bash
# Reddit
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret

# Product Hunt
PRODUCTHUNT_API_TOKEN=your_api_token

# Twitter/X
TWITTER_BEARER_TOKEN=your_bearer_token

# Fivetran
FIVETRAN_API_KEY=your_fivetran_key
FIVETRAN_API_SECRET=your_fivetran_secret
```

### Fivetran Setup

1. **Install Fivetran CLI**:
   ```bash
   pip install fivetran-client
   ```

2. **Configure Connectors**:
   ```python
   from connectors.reddit_connector.enhanced_reddit_connector import create_reddit_connector
   from connectors.producthunt_connector.enhanced_producthunt_connector import create_producthunt_connector
   from connectors.trends_connector.enhanced_trends_connector import create_trends_connector
   from connectors.twitter_connector.enhanced_twitter_connector import create_twitter_connector

   # Create connector instances
   reddit = create_reddit_connector(
       client_id=os.getenv('REDDIT_CLIENT_ID'),
       client_secret=os.getenv('REDDIT_CLIENT_SECRET')
   )

   # Similar for other connectors...
   ```

3. **Register with Fivetran**:
   - Use the Fivetran dashboard to register each connector
   - Configure sync schedules and data retention
   - Set up monitoring and alerts

## Data Model

### Standardized Fields

All connectors follow a consistent data model:

**Common Fields**:
- `id` - Unique identifier from source platform
- `created_at` - Timestamp when content was created
- `fivetran_synced` - When Fivetran synced the record
- `fivetran_deleted` - Soft delete flag
- `raw_data` - Complete original data payload

**Enrichment Fields**:
- `extracted_entities` - Companies, technologies, keywords
- `sentiment_analysis` - Emotional tone and confidence
- `idea_signals` - Business opportunities and pain points
- `market_insights` - Competitive and market analysis

### Cross-Platform Analytics

The database includes views for cross-platform analysis:

- `high_potential_ideas` - Top opportunities across all platforms
- `trending_keywords` - Popular terms with platform distribution
- `market_problems` - User problems and pain points
- `opportunity_summary` - Consolidated market opportunities

## Usage Examples

### Basic Data Extraction

```python
# Extract recent Reddit posts
reddit_connector = create_reddit_connector(config=reddit_config)
posts = await reddit_connector.extract_data('reddit_posts')

# Extract trending Product Hunt products
ph_connector = create_producthunt_connector(config=ph_config)
products = await ph_connector.extract_data('producthunt_products')
```

### Health Monitoring

```python
# Check connector health
health = await reddit_connector.health_check()
print(f"Reddit connector status: {health['status']}")
print(f"Tables: {health['tables_count']}")
print(f"Response time: {health['response_time_ms']}ms")
```

### Custom Analysis

```python
# Find high-potential ideas
query = """
SELECT title, description, platform, idea_potential_score
FROM consolidated_trends
WHERE idea_potential_score > 70
ORDER BY idea_potential_score DESC
LIMIT 10;
"""
```

## Performance and Scaling

### Rate Limiting

All connectors implement intelligent rate limiting:
- Respect platform API limits
- Automatic backoff on rate limit errors
- Configurable request rates per platform

### Batch Processing

- Process data in configurable batch sizes
- Parallel processing where supported
- Memory-efficient streaming for large datasets

### Error Handling

- Automatic retry with exponential backoff
- Dead letter queue for failed records
- Comprehensive error logging and monitoring

## Monitoring and Maintenance

### Health Checks

Each connector provides health monitoring:
```python
health = await connector.health_check()
# Returns: status, response_time_ms, tables_count, timestamp
```

### Logging

Comprehensive logging with different levels:
- `INFO`: Normal operations and metrics
- `WARNING`: Rate limiting and recoverable errors
- `ERROR`: Failed requests and data issues
- `DEBUG`: Detailed request/response data

### Metrics Tracking

Track key performance indicators:
- Records processed per sync
- API response times
- Error rates by type
- Data quality scores

## Security Considerations

### Credential Management

- Store API credentials in environment variables
- Use secret management in production
- Rotate keys regularly
- Principle of least privilege

### Data Privacy

- Redact sensitive user information
- Comply with platform terms of service
- Implement data retention policies
- Anonymize PII where possible

### Network Security

- Use HTTPS for all API calls
- Implement request signing where required
- Validate all incoming data
- Monitor for suspicious activity

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify API credentials are correct
   - Check for expired tokens
   - Ensure proper permissions

2. **Rate Limiting**
   - Reduce request frequency
   - Implement exponential backoff
   - Monitor usage against limits

3. **Data Quality Issues**
   - Check source platform for changes
   - Validate data transformation logic
   - Review extraction rules

4. **Performance Issues**
   - Increase batch sizes
   - Optimize database queries
   - Check network latency

### Debug Mode

Enable debug logging:
```python
config.enable_debug = True
```

### Support

For connector-specific issues:
1. Check platform API documentation
2. Review connector logs
3. Test with manual API calls
4. Contact platform support if needed

## Contributing

### Adding New Connectors

1. Inherit from `BaseConnector`
2. Implement required abstract methods
3. Follow naming conventions
4. Add comprehensive tests
5. Update documentation

### Code Standards

- Use type hints throughout
- Follow PEP 8 style guide
- Add docstrings for all methods
- Include error handling
- Write unit tests

### Testing

```bash
# Run unit tests
python -m pytest tests/

# Run integration tests
python -m pytest tests/integration/
```

## License

This connector suite is part of the IdeaGen project and follows the project's license terms.

## Changelog

### Version 1.0.0
- Initial release with Reddit, Product Hunt, Google Trends, and Twitter connectors
- Base connector framework with shared functionality
- Comprehensive database schema extensions
- Production-ready error handling and monitoring
- Cross-platform analytics and insights

---

**Built for the Fivetran Hackathon Challenge** - Demonstrating expertise in data pipeline automation and intelligent data transformation for idea generation.