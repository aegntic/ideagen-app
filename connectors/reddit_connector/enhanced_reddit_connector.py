"""
Enhanced Reddit Fivetran Connector for IdeaGen
Production-ready connector with comprehensive Reddit data extraction
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
class RedditConfig(ConnectorConfig):
    """Reddit-specific configuration"""
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    user_agent: str = "IdeaGen-Fivetran-Connector/1.0"
    subreddits: List[str] = None
    post_types: List[str] = None  # 'hot', 'new', 'top', 'rising'
    time_filter: str = 'day'  # 'hour', 'day', 'week', 'month', 'year', 'all'
    include_comments: bool = True
    max_comments_per_post: int = 100
    min_upvotes: int = 0
    search_keywords: List[str] = None

    def __post_init__(self):
        if self.subreddits is None:
            self.subreddits = ['entrepreneur', 'startups', 'SideProject', 'SaaS', 'indiehackers']
        if self.post_types is None:
            self.post_types = ['hot', 'top']
        if self.search_keywords is None:
            self.search_keywords = ['startup idea', 'business idea', 'side project', 'saas']


class RedditClient:
    """Reddit API client with OAuth2 authentication"""

    def __init__(self, config: RedditConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                headers={'User-Agent': self.config.user_agent}
            )

    async def _ensure_auth(self):
        """Ensure we have a valid access token"""
        if (self.access_token is None or
            (self.token_expires_at and datetime.now(UTC) >= self.token_expires_at)):
            await self._refresh_token()

    async def _refresh_token(self):
        """Refresh OAuth2 access token"""
        if not self.config.client_id or not self.config.client_secret:
            raise AuthenticationError("Reddit client_id and client_secret are required")

        await self._ensure_session()

        auth = aiohttp.BasicAuth(self.config.client_id, self.config.client_secret)
        data = {
            'grant_type': 'client_credentials'
        }

        try:
            async with self.session.post(
                'https://www.reddit.com/api/v1/access_token',
                auth=auth,
                data=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise AuthenticationError(f"Reddit auth failed: {response.status} - {error_text}")

                token_data = await response.json()
                self.access_token = token_data['access_token']
                # Set expiry time (Reddit tokens typically last 1 hour)
                self.token_expires_at = datetime.now(UTC) + timedelta(seconds=token_data.get('expires_in', 3600) - 60)

                self.logger.info("Reddit access token refreshed successfully")

        except Exception as e:
            raise AuthenticationError(f"Failed to refresh Reddit token: {str(e)}")

    async def make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request to Reddit API"""
        await self._ensure_session()
        await self._ensure_auth()

        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bearer {self.access_token}'
        kwargs['headers'] = headers

        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status == 401:
                    # Token might be expired, try to refresh
                    await self._refresh_token()
                    headers['Authorization'] = f'Bearer {self.access_token}'
                    kwargs['headers'] = headers

                    async with self.session.request(method, url, **kwargs) as retry_response:
                        if retry_response.status != 200:
                            error_text = await retry_response.text()
                            raise DataExtractionError(f"Reddit API error: {retry_response.status} - {error_text}")
                        return await retry_response.json()

                elif response.status != 200:
                    error_text = await response.text()
                    raise DataExtractionError(f"Reddit API error: {response.status} - {error_text}")

                return await response.json()

        except aiohttp.ClientError as e:
            raise DataExtractionError(f"Reddit API request failed: {str(e)}")

    async def get_subreddit_posts(self, subreddit: str, post_type: str = 'hot', limit: int = 100) -> List[Dict[str, Any]]:
        """Get posts from a subreddit"""
        url = f'https://oauth.reddit.com/r/{subreddit}/{post_type}'
        params = {
            'limit': min(limit, 100),  # Reddit max is 100
            't': self.config.time_filter if post_type == 'top' else None
        }
        params = {k: v for k, v in params.items() if v is not None}

        try:
            response = await self.make_request('GET', url, params=params)
            return response.get('data', {}).get('children', [])
        except Exception as e:
            self.logger.error(f"Failed to get posts from r/{subreddit}: {str(e)}")
            return []

    async def get_post_comments(self, post_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get comments for a post"""
        url = f'https://oauth.reddit.com/comments/{post_id}'
        params = {'limit': min(limit, 100)}

        try:
            response = await self.make_request('GET', url, params=params)
            # Reddit returns a list where the second element contains comments
            if len(response) > 1:
                return response[1].get('data', {}).get('children', [])
            return []
        except Exception as e:
            self.logger.error(f"Failed to get comments for post {post_id}: {str(e)}")
            return []

    async def search_posts(self, query: str, subreddit: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Search Reddit posts"""
        url = 'https://oauth.reddit.com/search'
        params = {
            'q': query,
            'limit': min(limit, 100),
            'sort': 'relevance',
            't': self.config.time_filter
        }
        if subreddit:
            params['restrict_sr'] = 'on'

        try:
            response = await self.make_request('GET', url, params=params)
            return response.get('data', {}).get('children', [])
        except Exception as e:
            self.logger.error(f"Failed to search Reddit for '{query}': {str(e)}")
            return []

    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()


class EnhancedRedditConnector(BaseConnector):
    """
    Enhanced Reddit connector for IdeaGen
    Extracts posts, comments, and subreddit data for idea generation
    """

    def __init__(self, config: RedditConfig = None):
        super().__init__(config or RedditConfig())
        self.reddit_client = RedditClient(self.config)

    async def get_tables(self) -> List[Table]:
        """Define Reddit connector tables"""
        tables = []

        # Posts table
        posts_columns = [
            self.create_column('id', DataType.STRING, primary_key=True),
            self.create_column('title', DataType.STRING, description='Post title'),
            self.create_column('author', DataType.STRING),
            self.create_column('subreddit', DataType.STRING),
            self.create_column('score', DataType.INTEGER),
            self.create_column('upvote_ratio', DataType.DECIMAL),
            self.create_column('num_comments', DataType.INTEGER),
            self.create_column('created_utc', DataType.TIMESTAMP),
            self.create_column('permalink', DataType.STRING),
            self.create_column('url', DataType.STRING),
            self.create_column('selftext', DataType.STRING),
            self.create_column('post_hint', DataType.STRING),
            self.create_column('domain', DataType.STRING),
            self.create_column('flair_text', DataType.STRING),
            self.create_column('is_self', DataType.BOOLEAN),
            self.create_column('over_18', DataType.BOOLEAN),
            self.create_column('awards', DataType.JSON),
            self.create_column('media_metadata', DataType.JSON),
            self.create_column('extracted_entities', DataType.JSON),
            self.create_column('idea_signals', DataType.JSON),
            self.create_column('raw_data', DataType.JSON)
        ]
        tables.append(self.create_table('reddit_posts', posts_columns))

        # Comments table
        comments_columns = [
            self.create_column('id', DataType.STRING, primary_key=True),
            self.create_column('post_id', DataType.STRING),
            self.create_column('author', DataType.STRING),
            self.create_column('body', DataType.STRING),
            self.create_column('score', DataType.INTEGER),
            self.create_column('created_utc', DataType.TIMESTAMP),
            self.create_column('depth', DataType.INTEGER),
            self.create_column('is_submitter', DataType.BOOLEAN),
            self.create_column('parent_id', DataType.STRING),
            self.create_column('edited', DataType.BOOLEAN),
            self.create_column('extracted_entities', DataType.JSON),
            self.create_column('idea_signals', DataType.JSON),
            self.create_column('raw_data', DataType.JSON)
        ]
        tables.append(self.create_table('reddit_comments', comments_columns))

        # Subreddits table
        subreddits_columns = [
            self.create_column('name', DataType.STRING, primary_key=True),
            self.create_column('title', DataType.STRING),
            self.create_column('description', DataType.STRING),
            self.create_column('subscribers', DataType.INTEGER),
            self.create_column('active_users', DataType.INTEGER),
            self.create_column('created_utc', DataType.TIMESTAMP),
            self.create_column('public_description', DataType.STRING),
            self.create_column('subreddit_type', DataType.STRING),
            self.create_column('over18', DataType.BOOLEAN),
            self.create_column('advertiser_category', DataType.STRING),
            self.create_column('key_color', DataType.STRING),
            self.create_column('icon_img', DataType.STRING),
            self.create_column('banner_img', DataType.STRING),
            self.create_column('raw_data', DataType.JSON)
        ]
        tables.append(self.create_table('reddit_subreddits', subreddits_columns))

        return tables

    async def extract_data(self, table_name: str, cursor: Optional[str] = None) -> List[DataRecord]:
        """Extract data for the specified table"""
        if table_name == 'reddit_posts':
            return await self._extract_posts(cursor)
        elif table_name == 'reddit_comments':
            return await self._extract_comments(cursor)
        elif table_name == 'reddit_subreddits':
            return await self._extract_subreddits(cursor)
        else:
            raise DataExtractionError(f"Unknown table: {table_name}")

    async def _extract_posts(self, cursor: Optional[str] = None) -> List[DataRecord]:
        """Extract Reddit posts"""
        records = []

        # Parse cursor to get timestamp if provided
        min_timestamp = None
        if cursor:
            try:
                min_timestamp = datetime.fromisoformat(cursor.replace('Z', '+00:00'))
            except:
                pass

        for subreddit in self.config.subreddits:
            for post_type in self.config.post_types:
                try:
                    posts = await self.reddit_client.get_subreddit_posts(
                        subreddit, post_type, self.config.batch_size
                    )

                    for post_data in posts:
                        post = post_data.get('data', {})

                        # Apply filters
                        if post.get('score', 0) < self.config.min_upvotes:
                            continue

                        created_at = DataTransformer.normalize_timestamp(post.get('created_utc'))
                        if min_timestamp and created_at <= min_timestamp:
                            continue

                        # Extract entities and idea signals
                        title = post.get('title', '')
                        selftext = post.get('selftext', '')

                        extracted_entities = self._extract_entities(title + ' ' + selftext)
                        idea_signals = self._detect_idea_signals(title, selftext, post)

                        record = DataRecord(
                            id=post.get('id'),
                            data={
                                'title': DataTransformer.sanitize_text(title),
                                'author': post.get('author'),
                                'subreddit': post.get('subreddit'),
                                'score': post.get('score', 0),
                                'upvote_ratio': post.get('upvote_ratio', 0),
                                'num_comments': post.get('num_comments', 0),
                                'created_utc': created_at.isoformat(),
                                'permalink': f"https://reddit.com{post.get('permalink', '')}",
                                'url': post.get('url'),
                                'selftext': DataTransformer.sanitize_text(selftext),
                                'post_hint': post.get('post_hint'),
                                'domain': DataTransformer.extract_domain(post.get('url', '')),
                                'flair_text': post.get('link_flair_text'),
                                'is_self': post.get('is_self', False),
                                'over_18': post.get('over_18', False),
                                'awards': post.get('total_awards_received', 0),
                                'media_metadata': post.get('media_metadata', {}),
                                'extracted_entities': extracted_entities,
                                'idea_signals': idea_signals,
                                'raw_data': post
                            },
                            timestamp=created_at,
                            source='reddit',
                            metadata={
                                'subreddit': subreddit,
                                'post_type': post_type,
                                'extraction_method': 'api'
                            }
                        )
                        records.append(record)

                except Exception as e:
                    self.logger.error(f"Error extracting posts from r/{subreddit}: {str(e)}")
                    continue

        # Also search for keyword-based posts
        for keyword in self.config.search_keywords:
            try:
                search_results = await self.reddit_client.search_posts(keyword, limit=50)

                for post_data in search_results:
                    post = post_data.get('data', {})

                    if post.get('score', 0) < self.config.min_upvotes:
                        continue

                    created_at = DataTransformer.normalize_timestamp(post.get('created_utc'))
                    if min_timestamp and created_at <= min_timestamp:
                        continue

                    title = post.get('title', '')
                    selftext = post.get('selftext', '')

                    extracted_entities = self._extract_entities(title + ' ' + selftext)
                    idea_signals = self._detect_idea_signals(title, selftext, post)

                    record = DataRecord(
                        id=post.get('id'),
                        data={
                            'title': DataTransformer.sanitize_text(title),
                            'author': post.get('author'),
                            'subreddit': post.get('subreddit'),
                            'score': post.get('score', 0),
                            'upvote_ratio': post.get('upvote_ratio', 0),
                            'num_comments': post.get('num_comments', 0),
                            'created_utc': created_at.isoformat(),
                            'permalink': f"https://reddit.com{post.get('permalink', '')}",
                            'url': post.get('url'),
                            'selftext': DataTransformer.sanitize_text(selftext),
                            'post_hint': post.get('post_hint'),
                            'domain': DataTransformer.extract_domain(post.get('url', '')),
                            'flair_text': post.get('link_flair_text'),
                            'is_self': post.get('is_self', False),
                            'over_18': post.get('over_18', False),
                            'awards': post.get('total_awards_received', 0),
                            'media_metadata': post.get('media_metadata', {}),
                            'extracted_entities': extracted_entities,
                            'idea_signals': idea_signals,
                            'raw_data': post
                        },
                        timestamp=created_at,
                        source='reddit',
                        metadata={
                            'search_keyword': keyword,
                            'extraction_method': 'search'
                        }
                    )
                    records.append(record)

            except Exception as e:
                self.logger.error(f"Error searching Reddit for '{keyword}': {str(e)}")
                continue

        # Sort by timestamp and limit
        records.sort(key=lambda x: x.timestamp, reverse=True)
        return records[:self.config.batch_size]

    async def _extract_comments(self, cursor: Optional[str] = None) -> List[DataRecord]:
        """Extract comments from recent posts"""
        records = []

        if not self.config.include_comments:
            return records

        # Get recent posts first
        recent_posts = await self._extract_posts(cursor)

        for post_record in recent_posts[:10]:  # Limit to 10 posts per batch
            try:
                comments = await self.reddit_client.get_post_comments(
                    post_record.id, self.config.max_comments_per_post
                )

                for comment_data in comments:
                    comment = comment_data.get('data', {})

                    if comment.get('score', 0) < 1:  # Skip low-quality comments
                        continue

                    created_at = DataTransformer.normalize_timestamp(comment.get('created_utc'))
                    body = comment.get('body', '')

                    extracted_entities = self._extract_entities(body)
                    idea_signals = self._detect_idea_signals('', body, comment)

                    record = DataRecord(
                        id=comment.get('id'),
                        data={
                            'post_id': post_record.id,
                            'author': comment.get('author'),
                            'body': DataTransformer.sanitize_text(body),
                            'score': comment.get('score', 0),
                            'created_utc': created_at.isoformat(),
                            'depth': comment.get('depth', 0),
                            'is_submitter': comment.get('is_submitter', False),
                            'parent_id': comment.get('parent_id'),
                            'edited': comment.get('edited', False),
                            'extracted_entities': extracted_entities,
                            'idea_signals': idea_signals,
                            'raw_data': comment
                        },
                        timestamp=created_at,
                        source='reddit',
                        metadata={
                            'post_id': post_record.id,
                            'post_title': post_record.data.get('title'),
                            'subreddit': post_record.data.get('subreddit')
                        }
                    )
                    records.append(record)

            except Exception as e:
                self.logger.error(f"Error extracting comments for post {post_record.id}: {str(e)}")
                continue

        records.sort(key=lambda x: x.timestamp, reverse=True)
        return records[:self.config.batch_size]

    async def _extract_subreddits(self, cursor: Optional[str] = None) -> List[DataRecord]:
        """Extract subreddit information"""
        records = []
        processed_subreddits = set()

        # Get subreddits from posts and from config
        subreddits_to_process = set(self.config.subreddits)

        # Add subreddits from recent posts
        recent_posts = await self._extract_posts(cursor)
        for post_record in recent_posts:
            subreddit = post_record.data.get('subreddit')
            if subreddit:
                subreddits_to_process.add(subreddit)

        for subreddit in subreddits_to_process:
            if subreddit in processed_subreddits:
                continue

            try:
                # Get subreddit info from a recent post
                url = f'https://oauth.reddit.com/r/{subreddit}/about'
                response = await self.reddit_client.make_request('GET', url)

                subreddit_data = response.get('data', {})
                if not subreddit_data:
                    continue

                created_at = DataTransformer.normalize_timestamp(subreddit_data.get('created_utc'))

                record = DataRecord(
                    id=subreddit_data.get('name', subreddit),
                    data={
                        'name': subreddit_data.get('name', subreddit),
                        'title': subreddit_data.get('title'),
                        'description': DataTransformer.sanitize_text(subreddit_data.get('public_description', '')),
                        'subscribers': subreddit_data.get('subscribers', 0),
                        'active_users': subreddit_data.get('active_user_count', 0),
                        'created_utc': created_at.isoformat(),
                        'public_description': DataTransformer.sanitize_text(subreddit_data.get('public_description', '')),
                        'subreddit_type': subreddit_data.get('subreddit_type'),
                        'over18': subreddit_data.get('over18', False),
                        'advertiser_category': subreddit_data.get('advertiser_category'),
                        'key_color': subreddit_data.get('key_color'),
                        'icon_img': subreddit_data.get('icon_img'),
                        'banner_img': subreddit_data.get('banner_img'),
                        'raw_data': subreddit_data
                    },
                    timestamp=created_at,
                    source='reddit',
                    metadata={'extraction_method': 'api'}
                )
                records.append(record)
                processed_subreddits.add(subreddit)

            except Exception as e:
                self.logger.error(f"Error extracting subreddit info for r/{subreddit}: {str(e)}")
                continue

        return records

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities from text (simple implementation)"""
        entities = {
            'urls': [],
            'mentions': [],
            'subreddits': [],
            'hashtags': [],
            'keywords': []
        }

        import re

        # Extract URLs
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        entities['urls'] = list(set(re.findall(url_pattern, text)))

        # Extract mentions
        mention_pattern = r'/u/(\w+)'
        entities['mentions'] = list(set(re.findall(mention_pattern, text)))

        # Extract subreddit references
        subreddit_pattern = r'/r/(\w+)'
        entities['subreddits'] = list(set(re.findall(subreddit_pattern, text)))

        # Extract hashtags
        hashtag_pattern = r'#(\w+)'
        entities['hashtags'] = list(set(re.findall(hashtag_pattern, text)))

        # Simple keyword extraction
        startup_keywords = [
            'startup', 'saas', 'business', 'entrepreneur', 'idea', 'product',
            'market', 'revenue', 'customer', 'user', 'platform', 'tool',
            'service', 'solution', 'innovation', 'technology', 'app'
        ]

        words = re.findall(r'\b\w+\b', text.lower())
        entities['keywords'] = [word for word in words if word in startup_keywords]

        return entities

    def _detect_idea_signals(self, title: str, body: str, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect signals that might indicate a business idea"""
        text = (title + ' ' + body).lower()
        score = post_data.get('score', 0)
        num_comments = post_data.get('num_comments', 0)

        signals = {
            'is_idea_request': False,
            'is_problem_statement': False,
            'is_success_story': False,
            'pain_points': [],
            'market_indicators': [],
            'idea_potential_score': 0
        }

        # Idea request patterns
        idea_request_patterns = [
            'looking for', 'any ideas', 'what do you think', 'feedback needed',
            'would you use', 'is there a market for', 'business idea',
            'startup idea', 'side project idea'
        ]

        for pattern in idea_request_patterns:
            if pattern in text:
                signals['is_idea_request'] = True
                break

        # Problem statement patterns
        problem_patterns = [
            'i hate', 'i wish', 'frustrated with', 'tired of', 'problem with',
            'struggle with', 'issue with', 'difficult to'
        ]

        for pattern in problem_patterns:
            if pattern in text:
                signals['is_problem_statement'] = True
                break

        # Success story patterns
        success_patterns = [
            'launched', 'successful', 'revenue', 'profit', 'customers',
            'traction', 'growth', 'milestone', 'achieved'
        ]

        for pattern in success_patterns:
            if pattern in text:
                signals['is_success_story'] = True
                break

        # Pain points extraction (simple)
        pain_indicators = ['expensive', 'slow', 'complicated', 'difficult', 'frustrating']
        signals['pain_points'] = [indicator for indicator in pain_indicators if indicator in text]

        # Market indicators
        market_indicators = ['growing', 'increasing', 'demand', 'market size', 'industry']
        signals['market_indicators'] = [indicator for indicator in market_indicators if indicator in text]

        # Calculate idea potential score
        idea_score = 0
        if signals['is_idea_request']:
            idea_score += 30
        if signals['is_problem_statement']:
            idea_score += 25
        if signals['pain_points']:
            idea_score += len(signals['pain_points']) * 10
        if signals['market_indicators']:
            idea_score += len(signals['market_indicators']) * 5
        if score > 100:
            idea_score += 15
        if num_comments > 50:
            idea_score += 10

        signals['idea_potential_score'] = min(idea_score, 100)

        return signals

    def get_cursor(self, record: DataRecord) -> str:
        """Generate cursor value for a record"""
        return record.timestamp.isoformat()

    async def cleanup(self):
        """Cleanup resources"""
        await self.reddit_client.close()
        await super().cleanup()


# Factory function
def create_reddit_connector(**kwargs) -> EnhancedRedditConnector:
    """Factory function to create Reddit connector"""
    config = RedditConfig(**kwargs)

    # Validate configuration
    errors = []
    if not config.client_id:
        errors.append("client_id is required")
    if not config.client_secret:
        errors.append("client_secret is required")

    if errors:
        raise ConfigurationError(f"Configuration errors: {'; '.join(errors)}")

    return EnhancedRedditConnector(config)