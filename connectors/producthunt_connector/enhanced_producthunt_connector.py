"""
Enhanced Product Hunt Fivetran Connector for IdeaGen
Production-ready connector with comprehensive Product Hunt data extraction
"""

import asyncio
import logging
import json
import hashlib
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Any, Optional, Set
import aiohttp
from dataclasses import dataclass

from ..base_connector import (
    BaseConnector, ConnectorConfig, DataRecord, RateLimiter,
    DataTransformer, Table, Column, DataType, ConfigurationError,
    AuthenticationError, DataExtractionError
)


@dataclass
class ProductHuntConfig(ConnectorConfig):
    """Product Hunt-specific configuration"""
    api_token: Optional[str] = None
    developer_token: Optional[str] = None
    base_url: str = "https://api.producthunt.com/v2"
    categories: List[str] = None
    topics: List[str] = None
    days_back: int = 7
    include_comments: bool = True
    min_votes: int = 5
    featured_only: bool = False
    sort_by: str = 'created_at'  # 'created_at', 'votes_count', 'comments_count'
    search_keywords: List[str] = None

    def __post_init__(self):
        if self.categories is None:
            self.categories = [
                'productivity', 'developer-tools', 'design', 'marketing',
                'saas', 'tech', 'artificial-intelligence', 'no-code',
                'api', 'open-source', 'entrepreneurship'
            ]
        if self.topics is None:
            self.topics = ['saas', 'b2b', 'productivity', 'developer-tools']
        if self.search_keywords is None:
            self.search_keywords = [
                'saas', 'startup tool', 'productivity', 'automation',
                'api', 'integration', 'workflow', 'b2b'
            ]


class ProductHuntClient:
    """Product Hunt API client with authentication"""

    def __init__(self, config: ProductHuntConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None or self.session.closed:
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'User-Agent': 'IdeaGen-Fivetran-Connector/1.0'
            }

            # Add authentication
            if self.config.api_token:
                headers['Authorization'] = f'Bearer {self.config.api_token}'
            elif self.config.developer_token:
                headers['Authorization'] = f'Bearer {self.config.developer_token}'

            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                headers=headers
            )

    def _ensure_auth(self):
        """Ensure authentication credentials are available"""
        if not self.config.api_token and not self.config.developer_token:
            raise AuthenticationError("Product Hunt API token or developer token is required")

    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request to Product Hunt API"""
        await self._ensure_session()
        self._ensure_auth()

        url = f"{self.config.base_url}{endpoint}"

        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status == 401:
                    raise AuthenticationError("Invalid Product Hunt API token")

                elif response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', '60'))
                    self.logger.warning(f"Rate limited, waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    async with self.session.request(method, url, **kwargs) as retry_response:
                        if retry_response.status != 200:
                            error_text = await retry_response.text()
                            raise DataExtractionError(f"Product Hunt API error: {retry_response.status} - {error_text}")
                        return await retry_response.json()

                elif response.status != 200:
                    error_text = await response.text()
                    raise DataExtractionError(f"Product Hunt API error: {response.status} - {error_text}")

                return await response.json()

        except aiohttp.ClientError as e:
            raise DataExtractionError(f"Product Hunt API request failed: {str(e)}")

    async def get_posts(
        self,
        days_back: int = 7,
        category: str = None,
        topic: str = None,
        sort_by: str = 'created_at',
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get Product Hunt posts with filters"""
        query_parts = []

        # Build GraphQL query
        graphql_query = """
        query getPosts($first: Int!, $after: String, $postedAfter: String, $postedBefore: String, $sortBy: PostSort!, $topic: String) {
            posts(first: $first, after: $after, postedAfter: $postedAfter, postedBefore: $postedBefore, sortBy: $sortBy, topic: $topic) {
                edges {
                    node {
                        id
                        name
                        tagline
                        description
                        url
                        website
                        createdAt
                        featuredAt
                        votesCount
                        commentsCount
                        reviewsCount
                        makers {
                            nodes {
                                id
                                name
                                username
                                headline
                                url
                                twitterUsername
                                profileImage
                            }
                        }
                        topics {
                            edges {
                                node {
                                    id
                                    name
                                    description
                                    slug
                                    stats {
                                        followersCount
                                        postsCount
                                    }
                                }
                            }
                        }
                        thumbnail {
                            url
                            type
                        }
                        media {
                            edges {
                                node {
                                    url
                                    type
                                    metadata
                                }
                            }
                        }
                        reviews(first: 10) {
                            edges {
                                node {
                                    id
                                    rating
                                    body
                                    createdAt
                                    user {
                                        id
                                        name
                                        username
                                        profileImage
                                    }
                                }
                            }
                        }
                        redirectUrl
                        slug
                        tagline
                        comments(first: 20) {
                            edges {
                                node {
                                    id
                                    body
                                    createdAt
                                    user {
                                        id
                                        name
                                        username
                                        profileImage
                                        twitterUsername
                                    }
                                    replies(first: 5) {
                                        edges {
                                            node {
                                                id
                                                body
                                                createdAt
                                                user {
                                                    id
                                                    name
                                                    username
                                                    profileImage
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """

        # Prepare variables
        variables = {
            'first': min(limit, 50),
            'sortBy': sort_by.upper(),
            'postedAfter': (datetime.now(UTC) - timedelta(days=days_back)).isoformat(),
            'postedBefore': datetime.now(UTC).isoformat()
        }

        if topic:
            variables['topic'] = topic

        # Make GraphQL request
        try:
            response = await self.make_request(
                'POST',
                '/api/graphql',
                json={
                    'query': graphql_query,
                    'variables': variables
                }
            )

            posts = []
            edges = response.get('data', {}).get('posts', {}).get('edges', [])

            for edge in edges:
                node = edge.get('node', {})
                if node:
                    posts.append(node)

            return posts

        except Exception as e:
            self.logger.error(f"Failed to get Product Hunt posts: {str(e)}")
            return []

    async def search_posts(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search Product Hunt posts"""
        graphql_query = """
        query searchPosts($query: String!, $first: Int!) {
            search(type: POST, query: $query, first: $first) {
                edges {
                    node {
                        ... on Post {
                            id
                            name
                            tagline
                            description
                            url
                            website
                            createdAt
                            featuredAt
                            votesCount
                            commentsCount
                            reviewsCount
                            makers {
                                nodes {
                                    id
                                    name
                                    username
                                    headline
                                    url
                                    twitterUsername
                                    profileImage
                                }
                            }
                            topics {
                                edges {
                                    node {
                                        id
                                        name
                                        description
                                        slug
                                        stats {
                                            followersCount
                                            postsCount
                                        }
                                    }
                                }
                            }
                            thumbnail {
                                url
                                type
                            }
                            media {
                                edges {
                                    node {
                                        url
                                        type
                                        metadata
                                    }
                                }
                            }
                            redirectUrl
                            slug
                        }
                    }
                }
            }
        }
        """

        try:
            response = await self.make_request(
                'POST',
                '/api/graphql',
                json={
                    'query': graphql_query,
                    'variables': {
                        'query': query,
                        'first': min(limit, 50)
                    }
                }
            )

            posts = []
            edges = response.get('data', {}).get('search', {}).get('edges', [])

            for edge in edges:
                node = edge.get('node', {})
                if node:
                    posts.append(node)

            return posts

        except Exception as e:
            self.logger.error(f"Failed to search Product Hunt posts: {str(e)}")
            return []

    async def get_topic_details(self, topic_slug: str) -> Dict[str, Any]:
        """Get details about a specific topic"""
        graphql_query = """
        query getTopic($slug: String!) {
            topic(slug: $slug) {
                id
                name
                description
                slug
                stats {
                    followersCount
                    postsCount
                }
                image {
                    url
                }
                createdAt
            }
        }
        """

        try:
            response = await self.make_request(
                'POST',
                '/api/graphql',
                json={
                    'query': graphql_query,
                    'variables': {
                        'slug': topic_slug
                    }
                }
            )

            return response.get('data', {}).get('topic', {})

        except Exception as e:
            self.logger.error(f"Failed to get topic details for {topic_slug}: {str(e)}")
            return {}

    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()


class EnhancedProductHuntConnector(BaseConnector):
    """
    Enhanced Product Hunt connector for IdeaGen
    Extracts products, makers, comments, and market insights for idea generation
    """

    def __init__(self, config: ProductHuntConfig = None):
        super().__init__(config or ProductHuntConfig())
        self.producthunt_client = ProductHuntClient(self.config)

    async def get_tables(self) -> List[Table]:
        """Define Product Hunt connector tables"""
        tables = []

        # Products table
        products_columns = [
            self.create_column('id', DataType.STRING, primary_key=True),
            self.create_column('name', DataType.STRING, description='Product name'),
            self.create_column('tagline', DataType.STRING),
            self.create_column('description', DataType.STRING),
            self.create_column('url', DataType.STRING),
            self.create_column('website', DataType.STRING),
            self.create_column('redirect_url', DataType.STRING),
            self.create_column('slug', DataType.STRING),
            self.create_column('created_at', DataType.TIMESTAMP),
            self.create_column('featured_at', DataType.TIMESTAMP),
            self.create_column('votes_count', DataType.INTEGER),
            self.create_column('comments_count', DataType.INTEGER),
            self.create_column('reviews_count', DataType.INTEGER),
            self.create_column('maker_count', DataType.INTEGER),
            self.create_column('thumbnail_url', DataType.STRING),
            self.create_column('media_urls', DataType.JSON),
            self.create_column('topics', DataType.JSON),
            self.create_column('makers', DataType.JSON),
            self.create_column('reviews', DataType.JSON),
            self.create_column('extracted_entities', DataType.JSON),
            self.create_column('market_signals', DataType.JSON),
            self.create_column('idea_potential', DataType.JSON),
            self.create_column('raw_data', DataType.JSON)
        ]
        tables.append(self.create_table('producthunt_products', products_columns))

        # Makers table
        makers_columns = [
            self.create_column('id', DataType.STRING, primary_key=True),
            self.create_column('name', DataType.STRING),
            self.create_column('username', DataType.STRING),
            self.create_column('headline', DataType.STRING),
            self.create_column('url', DataType.STRING),
            self.create_column('twitter_username', DataType.STRING),
            self.create_column('profile_image', DataType.STRING),
            self.create_column('follower_count', DataType.INTEGER),
            self.create_column('made_products_count', DataType.INTEGER),
            self.create_column('raw_data', DataType.JSON)
        ]
        tables.append(self.create_table('producthunt_makers', makers_columns))

        # Comments table
        comments_columns = [
            self.create_column('id', DataType.STRING, primary_key=True),
            self.create_column('product_id', DataType.STRING),
            self.create_column('user_id', DataType.STRING),
            self.create_column('user_name', DataType.STRING),
            self.create_column('username', DataType.STRING),
            self.create_column('body', DataType.STRING),
            self.create_column('created_at', DataType.TIMESTAMP),
            self.create_column('profile_image', DataType.STRING),
            self.create_column('twitter_username', DataType.STRING),
            self.create_column('reply_count', DataType.INTEGER),
            self.create_column('extracted_entities', DataType.JSON),
            self.create_column('sentiment_signals', DataType.JSON),
            self.create_column('raw_data', DataType.JSON)
        ]
        tables.append(self.create_table('producthunt_comments', comments_columns))

        # Topics table
        topics_columns = [
            self.create_column('id', DataType.STRING, primary_key=True),
            self.create_column('name', DataType.STRING),
            self.create_column('slug', DataType.STRING),
            self.create_column('description', DataType.STRING),
            self.create_column('followers_count', DataType.INTEGER),
            self.create_column('posts_count', DataType.INTEGER),
            self.create_column('image_url', DataType.STRING),
            self.create_column('created_at', DataType.TIMESTAMP),
            self.create_column('category', DataType.STRING),
            self.create_column('raw_data', DataType.JSON)
        ]
        tables.append(self.create_table('producthunt_topics', topics_columns))

        return tables

    async def extract_data(self, table_name: str, cursor: Optional[str] = None) -> List[DataRecord]:
        """Extract data for the specified table"""
        if table_name == 'producthunt_products':
            return await self._extract_products(cursor)
        elif table_name == 'producthunt_makers':
            return await self._extract_makers(cursor)
        elif table_name == 'producthunt_comments':
            return await self._extract_comments(cursor)
        elif table_name == 'producthunt_topics':
            return await self._extract_topics(cursor)
        else:
            raise DataExtractionError(f"Unknown table: {table_name}")

    async def _extract_products(self, cursor: Optional[str] = None) -> List[DataRecord]:
        """Extract Product Hunt products"""
        records = []

        # Parse cursor to get timestamp if provided
        min_timestamp = None
        if cursor:
            try:
                min_timestamp = datetime.fromisoformat(cursor.replace('Z', '+00:00'))
            except:
                pass

        # Get posts from topics and categories
        for topic in self.config.topics:
            try:
                posts = await self.producthunt_client.get_posts(
                    days_back=self.config.days_back,
                    topic=topic,
                    sort_by=self.config.sort_by,
                    limit=self.config.batch_size
                )

                for post in posts:
                    # Apply filters
                    if post.get('votesCount', 0) < self.config.min_votes:
                        continue

                    if self.config.featured_only and not post.get('featuredAt'):
                        continue

                    created_at = DataTransformer.normalize_timestamp(post.get('createdAt'))
                    if min_timestamp and created_at <= min_timestamp:
                        continue

                    # Extract and process data
                    topics_data = []
                    if post.get('topics', {}).get('edges'):
                        topics_data = [
                            edge.get('node', {}) for edge in post['topics']['edges']
                        ]

                    makers_data = []
                    if post.get('makers', {}).get('nodes'):
                        makers_data = post['makers']['nodes']

                    reviews_data = []
                    if post.get('reviews', {}).get('edges'):
                        reviews_data = [
                            edge.get('node', {}) for edge in post['reviews']['edges']
                        ]

                    media_urls = []
                    if post.get('media', {}).get('edges'):
                        media_urls = [
                            edge.get('node', {}).get('url')
                            for edge in post['media']['edges']
                            if edge.get('node', {}).get('url')
                        ]

                    # Extract entities and signals
                    title = post.get('name', '')
                    tagline = post.get('tagline', '')
                    description = post.get('description', '')

                    extracted_entities = self._extract_entities(title + ' ' + tagline + ' ' + description)
                    market_signals = self._detect_market_signals(post, topics_data, reviews_data)
                    idea_potential = self._assess_idea_potential(post, market_signals)

                    record = DataRecord(
                        id=post.get('id'),
                        data={
                            'name': DataTransformer.sanitize_text(title),
                            'tagline': DataTransformer.sanitize_text(tagline),
                            'description': DataTransformer.sanitize_text(description),
                            'url': post.get('url'),
                            'website': post.get('website'),
                            'redirect_url': post.get('redirectUrl'),
                            'slug': post.get('slug'),
                            'created_at': created_at.isoformat(),
                            'featured_at': DataTransformer.normalize_timestamp(post.get('featuredAt')).isoformat() if post.get('featuredAt') else None,
                            'votes_count': post.get('votesCount', 0),
                            'comments_count': post.get('commentsCount', 0),
                            'reviews_count': post.get('reviewsCount', 0),
                            'maker_count': len(makers_data),
                            'thumbnail_url': post.get('thumbnail', {}).get('url'),
                            'media_urls': media_urls,
                            'topics': topics_data,
                            'makers': makers_data,
                            'reviews': reviews_data,
                            'extracted_entities': extracted_entities,
                            'market_signals': market_signals,
                            'idea_potential': idea_potential,
                            'raw_data': post
                        },
                        timestamp=created_at,
                        source='producthunt',
                        metadata={
                            'topic': topic,
                            'extraction_method': 'topic_feed'
                        }
                    )
                    records.append(record)

            except Exception as e:
                self.logger.error(f"Error extracting products from topic '{topic}': {str(e)}")
                continue

        # Also search for keyword-based products
        for keyword in self.config.search_keywords:
            try:
                search_results = await self.producthunt_client.search_posts(keyword, limit=50)

                for post in search_results:
                    if post.get('votesCount', 0) < self.config.min_votes:
                        continue

                    created_at = DataTransformer.normalize_timestamp(post.get('createdAt'))
                    if min_timestamp and created_at <= min_timestamp:
                        continue

                    # Skip if we already have this product
                    if any(r.id == post.get('id') for r in records):
                        continue

                    # Process data similar to above
                    topics_data = []
                    if post.get('topics', {}).get('edges'):
                        topics_data = [
                            edge.get('node', {}) for edge in post['topics']['edges']
                        ]

                    title = post.get('name', '')
                    tagline = post.get('tagline', '')
                    description = post.get('description', '')

                    extracted_entities = self._extract_entities(title + ' ' + tagline + ' ' + description)
                    market_signals = self._detect_market_signals(post, topics_data, [])
                    idea_potential = self._assess_idea_potential(post, market_signals)

                    record = DataRecord(
                        id=post.get('id'),
                        data={
                            'name': DataTransformer.sanitize_text(title),
                            'tagline': DataTransformer.sanitize_text(tagline),
                            'description': DataTransformer.sanitize_text(description),
                            'url': post.get('url'),
                            'website': post.get('website'),
                            'redirect_url': post.get('redirectUrl'),
                            'slug': post.get('slug'),
                            'created_at': created_at.isoformat(),
                            'featured_at': DataTransformer.normalize_timestamp(post.get('featuredAt')).isoformat() if post.get('featuredAt') else None,
                            'votes_count': post.get('votesCount', 0),
                            'comments_count': post.get('commentsCount', 0),
                            'reviews_count': post.get('reviewsCount', 0),
                            'maker_count': len(post.get('makers', {}).get('nodes', [])),
                            'thumbnail_url': post.get('thumbnail', {}).get('url'),
                            'media_urls': [],
                            'topics': topics_data,
                            'makers': post.get('makers', {}).get('nodes', []),
                            'reviews': [],
                            'extracted_entities': extracted_entities,
                            'market_signals': market_signals,
                            'idea_potential': idea_potential,
                            'raw_data': post
                        },
                        timestamp=created_at,
                        source='producthunt',
                        metadata={
                            'search_keyword': keyword,
                            'extraction_method': 'search'
                        }
                    )
                    records.append(record)

            except Exception as e:
                self.logger.error(f"Error searching Product Hunt for '{keyword}': {str(e)}")
                continue

        # Sort by timestamp and limit
        records.sort(key=lambda x: x.timestamp, reverse=True)
        return records[:self.config.batch_size]

    async def _extract_makers(self, cursor: Optional[str] = None) -> List[DataRecord]:
        """Extract maker information from recent products"""
        records = []
        processed_makers = set()

        # Get recent products first
        recent_products = await self._extract_products(cursor)

        for product_record in recent_products:
            makers = product_record.data.get('makers', [])

            for maker in makers:
                maker_id = maker.get('id')
                if maker_id in processed_makers:
                    continue

                try:
                    record = DataRecord(
                        id=maker_id,
                        data={
                            'name': maker.get('name'),
                            'username': maker.get('username'),
                            'headline': maker.get('headline'),
                            'url': maker.get('url'),
                            'twitter_username': maker.get('twitterUsername'),
                            'profile_image': maker.get('profileImage'),
                            'follower_count': 0,  # Product Hunt doesn't provide this in basic API
                            'made_products_count': 1,  # We know they made at least this product
                            'raw_data': maker
                        },
                        timestamp=datetime.now(UTC),
                        source='producthunt',
                        metadata={
                            'product_id': product_record.id,
                            'product_name': product_record.data.get('name')
                        }
                    )
                    records.append(record)
                    processed_makers.add(maker_id)

                except Exception as e:
                    self.logger.error(f"Error processing maker {maker_id}: {str(e)}")
                    continue

        return records[:self.config.batch_size]

    async def _extract_comments(self, cursor: Optional[str] = None) -> List[DataRecord]:
        """Extract comments from recent products"""
        records = []

        if not self.config.include_comments:
            return records

        # Get recent products first
        recent_products = await self._extract_products(cursor)

        for product_record in recent_products[:20]:  # Limit to 20 products per batch
            try:
                # Comments are included in the product data from the API
                comments = product_record.raw_data.get('comments', {}).get('edges', [])

                for comment_edge in comments:
                    comment = comment_edge.get('node', {})

                    if not comment:
                        continue

                    created_at = DataTransformer.normalize_timestamp(comment.get('createdAt'))
                    body = comment.get('body', '')

                    extracted_entities = self._extract_entities(body)
                    sentiment_signals = self._analyze_sentiment(body)

                    record = DataRecord(
                        id=comment.get('id'),
                        data={
                            'product_id': product_record.id,
                            'user_id': comment.get('user', {}).get('id'),
                            'user_name': comment.get('user', {}).get('name'),
                            'username': comment.get('user', {}).get('username'),
                            'body': DataTransformer.sanitize_text(body),
                            'created_at': created_at.isoformat(),
                            'profile_image': comment.get('user', {}).get('profileImage'),
                            'twitter_username': comment.get('user', {}).get('twitterUsername'),
                            'reply_count': len(comment.get('replies', {}).get('edges', [])),
                            'extracted_entities': extracted_entities,
                            'sentiment_signals': sentiment_signals,
                            'raw_data': comment
                        },
                        timestamp=created_at,
                        source='producthunt',
                        metadata={
                            'product_id': product_record.id,
                            'product_name': product_record.data.get('name')
                        }
                    )
                    records.append(record)

            except Exception as e:
                self.logger.error(f"Error extracting comments for product {product_record.id}: {str(e)}")
                continue

        records.sort(key=lambda x: x.timestamp, reverse=True)
        return records[:self.config.batch_size]

    async def _extract_topics(self, cursor: Optional[str] = None) -> List[DataRecord]:
        """Extract topic information"""
        records = []
        processed_topics = set()

        # Get topics from recent products
        recent_products = await self._extract_products(cursor)

        for product_record in recent_products:
            topics = product_record.data.get('topics', [])

            for topic in topics:
                topic_id = topic.get('id')
                topic_slug = topic.get('slug')

                if topic_id in processed_topics or topic_slug in processed_topics:
                    continue

                try:
                    # Get detailed topic information
                    topic_details = await self.producthunt_client.get_topic_details(topic_slug)

                    created_at = DataTransformer.normalize_timestamp(topic_details.get('createdAt'))

                    record = DataRecord(
                        id=topic_id,
                        data={
                            'name': topic.get('name'),
                            'slug': topic.get('slug'),
                            'description': topic.get('description'),
                            'followers_count': topic.get('stats', {}).get('followersCount', 0),
                            'posts_count': topic.get('stats', {}).get('postsCount', 0),
                            'image_url': topic.get('image', {}).get('url'),
                            'created_at': created_at.isoformat() if topic_details.get('createdAt') else None,
                            'category': self._categorize_topic(topic.get('name', '')),
                            'raw_data': topic_details
                        },
                        timestamp=created_at if topic_details.get('createdAt') else datetime.now(UTC),
                        source='producthunt',
                        metadata={'extraction_method': 'api'}
                    )
                    records.append(record)
                    processed_topics.add(topic_id)

                except Exception as e:
                    self.logger.error(f"Error extracting topic {topic_id}: {str(e)}")
                    continue

        return records[:self.config.batch_size]

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities from text"""
        entities = {
            'urls': [],
            'mentions': [],
            'hashtags': [],
            'keywords': [],
            'technologies': [],
            'business_models': []
        }

        import re

        # Extract URLs
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        entities['urls'] = list(set(re.findall(url_pattern, text)))

        # Extract hashtags
        hashtag_pattern = r'#(\w+)'
        entities['hashtags'] = list(set(re.findall(hashtag_pattern, text)))

        # Technology keywords
        tech_keywords = [
            'api', 'saas', 'ai', 'ml', 'blockchain', 'cloud', 'mobile', 'web',
            'react', 'vue', 'angular', 'node', 'python', 'javascript', 'typescript',
            'docker', 'kubernetes', 'aws', 'gcp', 'azure', 'firebase', 'mongodb',
            'postgresql', 'mysql', 'redis', 'elasticsearch', 'graphql', 'rest'
        ]

        # Business model keywords
        business_keywords = [
            'subscription', 'freemium', 'b2b', 'b2c', 'marketplace', 'platform',
            'tool', 'service', 'software', 'application', 'product', 'solution',
            'automation', 'integration', 'analytics', 'dashboard', 'workflow'
        ]

        words = re.findall(r'\b\w+\b', text.lower())
        entities['technologies'] = [word for word in words if word in tech_keywords]
        entities['business_models'] = [word for word in words if word in business_keywords]
        entities['keywords'] = list(set(words))

        return entities

    def _detect_market_signals(self, post: Dict[str, Any], topics: List[Dict], reviews: List[Dict]) -> Dict[str, Any]:
        """Detect market signals from product data"""
        signals = {
            'trending_score': 0,
            'market_demand': 'low',
            'competition_level': 'unknown',
            'audience_size': 'unknown',
            'monetization_potential': 'medium',
            'technical_complexity': 'medium',
            'growth_indicators': [],
            'risk_factors': []
        }

        # Calculate trending score
        votes = post.get('votesCount', 0)
        comments = post.get('commentsCount', 0)
        reviews_count = post.get('reviewsCount', 0)

        trending_score = min((votes * 0.5 + comments * 2 + reviews_count * 5) / 100, 100)
        signals['trending_score'] = trending_score

        # Assess market demand
        if votes > 500:
            signals['market_demand'] = 'high'
        elif votes > 100:
            signals['market_demand'] = 'medium'

        # Competition assessment based on topics
        competitive_topics = ['saas', 'productivity', 'developer-tools', 'marketing']
        has_competitive_topic = any(
            topic.get('name', '').lower() in competitive_topics for topic in topics
        )
        signals['competition_level'] = 'high' if has_competitive_topic else 'medium'

        # Growth indicators
        if votes > 100:
            signals['growth_indicators'].append('high_engagement')
        if reviews_count > 10:
            signals['growth_indicators'].append('active_user_feedback')
        if len(topics) > 3:
            signals['growth_indicators'].append('multi_market_appeal')

        # Risk factors
        if votes < 50:
            signals['risk_factors'].append('low_validation')
        if not post.get('website'):
            signals['risk_factors'].append('no_landing_page')
        if not post.get('description'):
            signals['risk_factors'].append('incomplete_listing')

        return signals

    def _assess_idea_potential(self, post: Dict[str, Any], signals: Dict[str, Any]) -> Dict[str, Any]:
        """Assess the potential of this product as an idea inspiration"""
        potential = {
            'overall_score': 0,
            'market_fit': 'unknown',
            'innovation_level': 'medium',
            'scalability': 'medium',
            'monetization_likelihood': 'medium',
            'competitive_advantage': 'low',
            'user_problem_solved': 'unknown',
            'recommendations': []
        }

        # Calculate overall score
        score_components = [
            signals['trending_score'] * 0.3,
            min(post.get('votesCount', 0) / 10, 30) * 0.2,
            min(post.get('commentsCount', 0) / 5, 20) * 0.2,
            min(len(post.get('makers', [])) * 5, 10) * 0.1,
            min(post.get('reviewsCount', 0) * 2, 10) * 0.2
        ]

        potential['overall_score'] = min(sum(score_components), 100)

        # Market fit assessment
        if signals['market_demand'] == 'high':
            potential['market_fit'] = 'strong'
        elif signals['market_demand'] == 'medium':
            potential['market_fit'] = 'moderate'

        # Innovation assessment based on description uniqueness
        description = post.get('description', '').lower()
        innovation_keywords = ['first', 'revolutionary', 'breakthrough', 'innovative', 'unique']
        if any(keyword in description for keyword in innovation_keywords):
            potential['innovation_level'] = 'high'

        # Generate recommendations
        if potential['overall_score'] > 70:
            potential['recommendations'].append('High potential - consider similar approach')
        if signals['competition_level'] == 'high':
            potential['recommendations'].append('Competitive market - find unique angle')
        if not post.get('website'):
            potential['recommendations'].append('Missing website - opportunity for improvement')
        if post.get('votesCount', 0) > 200:
            potential['recommendations'].append('Strong validation - user problem confirmed')

        return potential

    def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Simple sentiment analysis"""
        positive_words = ['love', 'amazing', 'great', 'awesome', 'fantastic', 'perfect', 'excellent']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'worst', 'disappointed', 'poor']

        words = text.lower().split()
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)

        if positive_count > negative_count:
            sentiment = 'positive'
        elif negative_count > positive_count:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        return {
            'sentiment': sentiment,
            'positive_words': positive_count,
            'negative_words': negative_count,
            'confidence': abs(positive_count - negative_count) / max(len(words), 1)
        }

    def _categorize_topic(self, topic_name: str) -> str:
        """Categorize a topic into broader categories"""
        topic_lower = topic_name.lower()

        categories = {
            'technology': ['tech', 'developer', 'api', 'software', 'coding', 'programming'],
            'business': ['business', 'entrepreneur', 'startup', 'saas', 'b2b', 'marketing'],
            'productivity': ['productivity', 'tools', 'efficiency', 'workflow', 'automation'],
            'design': ['design', 'ui', 'ux', 'interface', 'creative'],
            'mobile': ['mobile', 'ios', 'android', 'app'],
            'data': ['data', 'analytics', 'database', 'metrics', 'insights']
        }

        for category, keywords in categories.items():
            if any(keyword in topic_lower for keyword in keywords):
                return category

        return 'other'

    def get_cursor(self, record: DataRecord) -> str:
        """Generate cursor value for a record"""
        return record.timestamp.isoformat()

    async def cleanup(self):
        """Cleanup resources"""
        await self.producthunt_client.close()
        await super().cleanup()


# Factory function
def create_producthunt_connector(**kwargs) -> EnhancedProductHuntConnector:
    """Factory function to create Product Hunt connector"""
    config = ProductHuntConfig(**kwargs)

    # Validate configuration
    errors = []
    if not config.api_token and not config.developer_token:
        errors.append("api_token or developer_token is required")

    if errors:
        raise ConfigurationError(f"Configuration errors: {'; '.join(errors)}")

    return EnhancedProductHuntConnector(config)