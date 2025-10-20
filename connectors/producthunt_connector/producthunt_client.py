"""
Product Hunt API Client
Handles communication with Product Hunt API
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime, UTC, timedelta
import backoff
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import get_config


logger = logging.getLogger(__name__)


class ProductHuntClient:
    """Product Hunt API client with error handling and retry logic"""

    def __init__(self, config=None):
        self.config = config or get_config()
        self.base_url = "https://api.producthunt.com/v2"
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self.config.developer_token,
            "X-API-KEY": self.config.api_key
        }

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3,
        base=60,
        max_value=300
    )
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to Product Hunt API"""
        url = f"{self.base_url}/{endpoint}"

        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 401:
                        raise Exception("Authentication failed - check API credentials")
                    elif response.status == 429:
                        retry_after = int(response.headers.get('Retry-After', 60))
                        raise Exception(f"Rate limited. Retry after {retry_after} seconds")
                    else:
                        error_text = await response.text()
                        raise Exception(f"API request failed: {response.status} - {error_text}")

            except aiohttp.ClientError as e:
                logger.error(f"HTTP client error: {e}")
                raise
            except asyncio.TimeoutError as e:
                logger.error(f"Request timeout: {e}")
                raise

    async def get_trending_posts(
        self,
        days_back: Optional[int] = None,
        limit: Optional[int] = None,
        categories: Optional[List[str]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch trending posts from Product Hunt

        Args:
            days_back: Number of days to look back
            limit: Maximum number of posts to fetch
            categories: List of categories to filter by

        Yields:
            Dict containing product data
        """
        days_back = days_back or self.config.days_back
        limit = limit or self.config.posts_limit
        categories = categories or self.config.categories

        try:
            # Get posts from recent days
            end_date = datetime.now(UTC)
            start_date = end_date - timedelta(days=days_back)

            # GraphQL query for posts
            query = """
            query GetPosts($after: String, $order: PostOrder, $postedIn: [String]) {
              posts(first: 50, after: $after, order: $order, postedIn: $postedIn) {
                edges {
                  node {
                    id
                    name
                    tagline
                    description
                    slug
                    url
                    website
                    votesCount
                    commentsCount
                    featuredAt
                    createdAt
                    day
                    reviewsCount
                    productState
                    redirectUrl
                    screenshotUrl
                    thumbnail {
                      url
                    }
                    topics {
                      edges {
                        node {
                          id
                          name
                          slug
                        }
                      }
                    }
                    user {
                      id
                      name
                      username
                      url
                      headline
                      bio
                      profileImage
                    }
                    makers {
                      edges {
                        node {
                          id
                          name
                          username
                          url
                          headline
                          profileImage
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

            variables = {
                "order": "VOTES",
                "postedIn": [start_date.strftime("%Y-%m-%d")]
            }

            posts_fetched = 0
            has_next_page = True
            cursor = None

            while has_next_page and posts_fetched < limit:
                if cursor:
                    variables["after"] = cursor

                try:
                    response = await self._make_request(
                        method="POST",
                        endpoint="api/graphql",
                        json_data={"query": query, "variables": variables}
                    )

                    posts_data = response.get("data", {}).get("posts", {})
                    edges = posts_data.get("edges", [])

                    for edge in edges:
                        if posts_fetched >= limit:
                            break

                        post_node = edge.get("node", {})
                        if post_node:
                            # Transform and enhance post data
                            transformed_post = self._transform_post_data(post_node)

                            # Add idea generation metrics
                            transformed_post.update(self._calculate_idea_metrics(post_node))

                            yield transformed_post
                            posts_fetched += 1

                    # Check pagination
                    page_info = posts_data.get("pageInfo", {})
                    has_next_page = page_info.get("hasNextPage", False)
                    cursor = page_info.get("endCursor")

                except Exception as e:
                    logger.warning(f"Error fetching posts batch: {e}")
                    break

        except Exception as e:
            logger.error(f"Error fetching trending posts: {e}")
            raise

    async def get_post_comments(
        self,
        post_id: str,
        limit: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch comments for a specific post

        Args:
            post_id: Product Hunt post ID
            limit: Maximum number of comments to fetch

        Yields:
            Dict containing comment data
        """
        limit = limit or self.config.comments_limit

        try:
            query = """
            query GetPostComments($postId: ID!, $after: String) {
              post(id: $postId) {
                comments(first: 50, after: $after, order: RANKING) {
                  edges {
                    node {
                      id
                      body
                      createdAt
                      user {
                        id
                        name
                        username
                        headline
                        profileImage
                      }
                      parent {
                        id
                      }
                      childCommentsCount
                      votesCount
                      truncated
                      deleted
                    }
                  }
                  pageInfo {
                    hasNextPage
                    endCursor
                  }
                }
              }
            }
            """

            variables = {"postId": post_id}
            comments_fetched = 0
            has_next_page = True
            cursor = None

            while has_next_page and comments_fetched < limit:
                if cursor:
                    variables["after"] = cursor

                try:
                    response = await self._make_request(
                        method="POST",
                        endpoint="api/graphql",
                        json_data={"query": query, "variables": variables}
                    )

                    post_data = response.get("data", {}).get("post", {})
                    comments_data = post_data.get("comments", {})
                    edges = comments_data.get("edges", [])

                    for edge in edges:
                        if comments_fetched >= limit:
                            break

                        comment_node = edge.get("node", {})
                        if comment_node:
                            # Transform and analyze comment data
                            transformed_comment = self._transform_comment_data(comment_node, post_id)

                            # Add sentiment analysis and insights
                            transformed_comment.update(self._analyze_comment_for_insights(comment_node))

                            yield transformed_comment
                            comments_fetched += 1

                    # Check pagination
                    page_info = comments_data.get("pageInfo", {})
                    has_next_page = page_info.get("hasNextPage", False)
                    cursor = page_info.get("endCursor")

                except Exception as e:
                    logger.warning(f"Error fetching comments batch: {e}")
                    break

        except Exception as e:
            logger.error(f"Error fetching post comments for {post_id}: {e}")

    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get available categories from Product Hunt"""
        try:
            query = """
            query GetCategories {
              topics {
                edges {
                  node {
                    id
                    name
                    slug
                    description
                    color
                    featured
                    position
                    apiSlug
                  }
                }
              }
            }
            """

            response = await self._make_request(
                method="POST",
                endpoint="api/graphql",
                json_data={"query": query}
            )

            topics_data = response.get("data", {}).get("topics", {})
            edges = topics_data.get("edges", [])

            categories = []
            for edge in edges:
                topic_node = edge.get("node", {})
                if topic_node:
                    transformed_category = self._transform_category_data(topic_node)
                    categories.append(transformed_category)

            return categories

        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    def _transform_post_data(self, post_node: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Product Hunt post data to standardized format"""
        topics = post_node.get("topics", {}).get("edges", [])
        topic_ids = [topic.get("node", {}).get("id") for topic in topics]
        topic_names = [topic.get("node", {}).get("name") for topic in topics]

        user = post_node.get("user", {})
        makers = post_node.get("makers", {}).get("edges", [])
        maker_ids = [maker.get("node", {}).get("id") for maker in makers]

        thumbnail_data = post_node.get("thumbnail", {})
        thumbnail_url = thumbnail_data.get("url") if thumbnail_data else None

        return {
            "id": post_node.get("id"),
            "name": post_node.get("name"),
            "tagline": post_node.get("tagline"),
            "description": post_node.get("description"),
            "slug": post_node.get("slug"),
            "url": post_node.get("url"),
            "website": post_node.get("website"),
            "votes_count": post_node.get("votesCount", 0),
            "comments_count": post_node.get("commentsCount", 0),
            "featured_at": post_node.get("featuredAt"),
            "created_at": post_node.get("createdAt"),
            "day": post_node.get("day"),
            "category_id": topic_ids[0] if topic_ids else None,
            "topic_ids": ",".join(topic_ids) if topic_ids else None,
            "user_id": user.get("id"),
            "maker_id": maker_ids[0] if maker_ids else None,
            "redirect_url": post_node.get("redirectUrl"),
            "screenshot_url": post_node.get("screenshotUrl"),
            "thumbnail_url": thumbnail_url,
            "reviews_count": post_node.get("reviewsCount", 0),
            "current_user_reviewed": False,
            "product_state": post_node.get("productState"),
            "ios_url": None,  # Not available in API v2
            "android_url": None,  # Not available in API v2
            "web_url": post_node.get("website"),
            "extracted_at": datetime.now(UTC).isoformat()
        }

    def _transform_comment_data(self, comment_node: Dict[str, Any], post_id: str) -> Dict[str, Any]:
        """Transform Product Hunt comment data to standardized format"""
        user = comment_node.get("user", {})
        parent = comment_node.get("parent", {})

        return {
            "id": comment_node.get("id"),
            "body": comment_node.get("body"),
            "created_at": comment_node.get("createdAt"),
            "user_id": user.get("id"),
            "post_id": post_id,
            "parent_id": parent.get("id") if parent else None,
            "child_comments_count": comment_node.get("childCommentsCount", 0),
            "votes_count": comment_node.get("votesCount", 0),
            "truncated": comment_node.get("truncated", False),
            "deleted": comment_node.get("deleted", False),
            "extracted_at": datetime.now(UTC).isoformat()
        }

    def _transform_category_data(self, topic_node: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Product Hunt topic/category data to standardized format"""
        return {
            "id": topic_node.get("id"),
            "name": topic_node.get("name"),
            "slug": topic_node.get("slug"),
            "description": topic_node.get("description"),
            "color": topic_node.get("color"),
            "featured": topic_node.get("featured", False),
            "position": topic_node.get("position", 0),
            "api_slug": topic_node.get("apiSlug"),
            "extracted_at": datetime.now(UTC).isoformat(),
            "trend_score": 0.0,  # Would calculate based on recent activity
            "market_opportunity": None  # Would analyze market trends
        }

    def _calculate_idea_metrics(self, post_node: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate idea generation metrics for a product"""
        votes = post_node.get("votesCount", 0)
        comments = post_node.get("commentsCount", 0)
        name = post_node.get("name", "").lower()
        tagline = post_node.get("tagline", "").lower()
        description = post_node.get("description", "").lower()

        text_content = f"{name} {tagline} {description}"

        # Calculate engagement score
        engagement_score = min(1.0, (votes + comments * 2) / 1000.0)

        # Idea generation indicators
        idea_keywords = [
            "ai", "automation", "productivity", "tool", "platform", "service",
            "app", "software", "solution", "startup", "business", "market",
            "analytics", "dashboard", "api", "integration", "workflow"
        ]

        keyword_matches = sum(1 for keyword in idea_keywords if keyword in text_content)
        idea_score = min(1.0, keyword_matches / 8.0)

        # Market validation based on engagement
        market_validation = []
        if votes > 500:
            market_validation.append("high_user_interest")
        if comments > 100:
            market_validation.append("active_community")
        if post_node.get("reviewsCount", 0) > 50:
            market_validation.append("positive_reviews")

        # Trend signals
        trend_signals = []
        topics = post_node.get("topics", {}).get("edges", [])
        topic_names = [topic.get("node", {}).get("name", "").lower() for topic in topics]

        trending_topics = ["ai", "productivity", "remote work", "sustainability", "fintech"]
        for topic in trending_topics:
            if any(topic in t for t in topic_names):
                trend_signals.append(f"{topic}_trending")

        # Competition analysis
        competition_keywords = ["alternative", "better than", "replacement", "vs"]
        competition_signals = sum(1 for kw in competition_keywords if kw in text_content)

        return {
            "idea_generation_score": round(idea_score, 2),
            "market_validation": ",".join(market_validation) if market_validation else None,
            "trend_signals": ",".join(trend_signals) if trend_signals else None,
            "competition_analysis": f"competition_signals:{competition_signals}"
        }

    def _analyze_comment_for_insights(self, comment_node: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze comment for market insights and feedback"""
        body = comment_node.get("body", "").lower()

        # Sentiment analysis (simplified)
        positive_words = ["love", "awesome", "great", "amazing", "perfect", "excellent"]
        negative_words = ["hate", "terrible", "awful", "bad", "useless", "disappointed"]

        positive_count = sum(1 for word in positive_words if word in body)
        negative_count = sum(1 for word in negative_words if word in body)

        total_sentiment_words = positive_count + negative_count
        sentiment_score = 0.0
        if total_sentiment_words > 0:
            sentiment_score = (positive_count - negative_count) / total_sentiment_words

        # Feedback type classification
        feedback_types = []
        if any(word in body for word in ["suggestion", "should", "could", "add", "feature"]):
            feedback_types.append("feature_request")
        if any(word in body for word in ["bug", "broken", "issue", "problem", "doesn't work"]):
            feedback_types.append("bug_report")
        if any(word in body for word in ["price", "cost", "expensive", "cheap", "free"]):
            feedback_types.append("pricing_feedback")
        if any(word in body for word in ["design", "ui", "ux", "interface", "look"]):
            feedback_types.append("design_feedback")

        # Feature requests
        feature_keywords = ["wish", "need", "want", "add", "implement", "create"]
        feature_requests = []
        for keyword in feature_keywords:
            if keyword in body:
                # Extract sentence containing the keyword (simplified)
                sentences = body.split(".")
                for sentence in sentences:
                    if keyword in sentence:
                        feature_requests.append(sentence.strip())
                        break

        # Pain points
        pain_keywords = ["frustrated", "difficult", "annoying", "problem", "issue"]
        pain_points = []
        for keyword in pain_keywords:
            if keyword in body:
                sentences = body.split(".")
                for sentence in sentences:
                    if keyword in sentence:
                        pain_points.append(sentence.strip())
                        break

        # Market insights
        market_insights = []
        if any(word in body for word in ["competitor", "alternative", "vs", "compare"]):
            market_insights.append("competitor_mentioned")
        if any(word in body for word in ["market", "industry", "business", "company"]):
            market_insights.append("business_context")
        if any(word in body for word in ["recommend", "suggest", "tell", "share"]):
            market_insights.append("advocacy_signal")

        return {
            "sentiment_score": round(sentiment_score, 2),
            "feedback_type": ",".join(feedback_types) if feedback_types else None,
            "feature_requests": " | ".join(feature_requests) if feature_requests else None,
            "pain_points": " | ".join(pain_points) if pain_points else None,
            "market_insights": ",".join(market_insights) if market_insights else None
        }