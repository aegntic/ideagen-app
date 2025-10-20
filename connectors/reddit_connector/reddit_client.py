"""
Reddit API Client
Handles communication with Reddit API using PRAW
"""

import praw
import asyncio
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime, UTC
from prawcore.exceptions import (
    RequestException,
    ResponseException,
    OAuthException,
    Forbidden,
    NotFound
)
import backoff
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import get_config


logger = logging.getLogger(__name__)


class RedditClient:
    """Reddit API client with error handling and retry logic"""

    def __init__(self, config=None):
        self.config = config or get_config()
        self.reddit = None
        self._initialize_reddit()

    def _initialize_reddit(self):
        """Initialize Reddit API client"""
        try:
            self.reddit = praw.Reddit(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                user_agent=self.config.user_agent,
                read_only=True
            )
            # Test connection
            logger.info(f"Connected to Reddit as: {self.reddit.user.me()}")
        except Exception as e:
            logger.error(f"Failed to initialize Reddit client: {e}")
            raise

    @backoff.on_exception(
        backoff.expo,
        (RequestException, ResponseException, OAuthException),
        max_tries=3,
        base=60,
        max_value=300
    )
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def get_trending_posts(
        self,
        subreddit_names: Optional[List[str]] = None,
        post_limit: Optional[int] = None,
        time_filter: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch trending posts from specified subreddits

        Args:
            subreddit_names: List of subreddit names to fetch from
            post_limit: Number of posts to fetch per subreddit
            time_filter: Time period to filter by (hour, day, week, month, year, all)

        Yields:
            Dict containing post data
        """
        subreddits = subreddit_names or self.config.subreddits
        limit = post_limit or self.config.post_limit
        time_filter = time_filter or self.config.time_filter

        for subreddit_name in subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)

                # Get trending posts
                for submission in subreddit.top(time_filter=time_filter, limit=limit):
                    try:
                        post_data = self._transform_post_data(submission)

                        # Add idea generation metrics
                        post_data.update(self._calculate_idea_metrics(submission))

                        yield post_data

                    except Exception as e:
                        logger.warning(f"Error processing post {submission.id}: {e}")
                        continue

            except (Forbidden, NotFound) as e:
                logger.warning(f"Cannot access subreddit {subreddit_name}: {e}")
                continue
            except Exception as e:
                logger.error(f"Error fetching from subreddit {subreddit_name}: {e}")
                continue

    @backoff.on_exception(
        backoff.expo,
        (RequestException, ResponseException),
        max_tries=3,
        base=60
    )
    async def get_post_comments(
        self,
        post_id: str,
        comment_limit: Optional[int] = None,
        sort: str = "best"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch comments for a specific post

        Args:
            post_id: Reddit post ID
            comment_limit: Number of comments to fetch
            sort: Comment sort method (best, top, new, controversial)

        Yields:
            Dict containing comment data
        """
        limit = comment_limit or self.config.comment_limit

        try:
            submission = self.reddit.submission(id=post_id)
            submission.comment_sort = sort
            submission.comments.replace_more(limit=0)

            for comment in submission.comments.list()[:limit]:
                try:
                    comment_data = self._transform_comment_data(comment, post_id)

                    # Add sentiment analysis and idea extraction
                    comment_data.update(self._analyze_comment_for_ideas(comment))

                    yield comment_data

                except Exception as e:
                    logger.warning(f"Error processing comment {comment.id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error fetching comments for post {post_id}: {e}")

    async def get_subreddit_info(self, subreddit_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a subreddit

        Args:
            subreddit_name: Name of the subreddit

        Returns:
            Dict containing subreddit data
        """
        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            return {
                "name": subreddit.display_name,
                "title": subreddit.title,
                "description": subreddit.public_description,
                "subscribers": subreddit.subscribers,
                "active_users": subreddit.active_user_count,
                "created_utc": datetime.fromtimestamp(subreddit.created_utc, UTC).isoformat(),
                "public_description": subreddit.public_description,
                "icon_img": subreddit.icon_img,
                "banner_img": subreddit.banner_img,
                "over18": subreddit.over18,
                "advertiser_category": subreddit.advertiser_category,
                "extracted_at": datetime.now(UTC).isoformat(),
                "engagement_rate": self._calculate_engagement_rate(subreddit),
                "growth_trend": self._analyze_growth_trend(subreddit)
            }
        except Exception as e:
            logger.error(f"Error getting subreddit info for {subreddit_name}: {e}")
            return {}

    def _transform_post_data(self, submission) -> Dict[str, Any]:
        """Transform Reddit submission data to standardized format"""
        return {
            "id": submission.id,
            "title": submission.title,
            "author": str(submission.author) if submission.author else "[deleted]",
            "subreddit": submission.subreddit.display_name,
            "score": submission.score,
            "num_comments": submission.num_comments,
            "upvote_ratio": submission.upvote_ratio,
            "created_utc": datetime.fromtimestamp(submission.created_utc, UTC).isoformat(),
            "url": submission.url,
            "selftext": submission.selftext or "",
            "permalink": f"https://reddit.com{submission.permalink}",
            "is_self": submission.is_self,
            "over_18": submission.over_18,
            "spoiler": submission.spoiler,
            "stickied": submission.stickied,
            "distinguished": submission.distinguished or None,
            "flair_text": submission.link_flair_text,
            "awards": len(submission.all_awardings) if hasattr(submission, 'all_awardings') else 0,
            "post_hint": getattr(submission, 'post_hint', None),
            "domain": submission.domain,
            "extracted_at": datetime.now(UTC).isoformat()
        }

    def _transform_comment_data(self, comment, post_id: str) -> Dict[str, Any]:
        """Transform Reddit comment data to standardized format"""
        return {
            "id": comment.id,
            "post_id": post_id,
            "author": str(comment.author) if comment.author else "[deleted]",
            "body": comment.body,
            "score": comment.score,
            "created_utc": datetime.fromtimestamp(comment.created_utc, UTC).isoformat(),
            "permalink": f"https://reddit.com{comment.permalink}",
            "is_submitter": comment.is_submitter,
            "distinguished": comment.distinguished or None,
            "stickied": comment.stickied,
            "replies": len(comment.replies.list()) if hasattr(comment, 'replies') else 0,
            "depth": comment.depth if hasattr(comment, 'depth') else 0,
            "extracted_at": datetime.now(UTC).isoformat()
        }

    def _calculate_idea_metrics(self, submission) -> Dict[str, Any]:
        """Calculate idea generation metrics for a post"""
        title_lower = submission.title.lower()
        text_content = (submission.title + " " + (submission.selftext or "")).lower()

        # Idea generation indicators
        idea_keywords = [
            "looking for", "need", "wish there was", "problem", "frustrated",
            "build", "create", "startup", "business", "idea", "opportunity",
            "market", "solution", "app", "tool", "platform", "service"
        ]

        keyword_matches = sum(1 for keyword in idea_keywords if keyword in text_content)

        # Calculate idea generation score (0-1)
        idea_score = min(1.0, keyword_matches / 5.0)  # Normalize to 0-1

        # Extract trending topics from title and content
        trending_topics = self._extract_topics(text_content)

        # Identify market signals
        market_signals = self._identify_market_signals(text_content, submission.score)

        return {
            "idea_generation_score": round(idea_score, 2),
            "trending_topics": ",".join(trending_topics) if trending_topics else None,
            "market_signals": ",".join(market_signals) if market_signals else None
        }

    def _analyze_comment_for_ideas(self, comment) -> Dict[str, Any]:
        """Analyze comment for pain points and feature requests"""
        body_lower = comment.body.lower()

        # Pain point indicators
        pain_point_keywords = [
            "problem", "issue", "bug", "broken", "doesn't work", "frustrating",
            "annoying", "hate", "wish", "difficult", "complicated", "confusing"
        ]

        # Feature request indicators
        feature_keywords = [
            "would be nice", "should have", "need", "want", "feature",
            "add", "implement", "create", "build", "make it", "if only"
        ]

        pain_points = [kw for kw in pain_point_keywords if kw in body_lower]
        feature_requests = [kw for kw in feature_keywords if kw in body_lower]

        # Simple sentiment based on keywords
        positive_words = ["love", "great", "awesome", "perfect", "excellent", "amazing"]
        negative_words = ["hate", "terrible", "awful", "broken", "useless", "worst"]

        positive_count = sum(1 for word in positive_words if word in body_lower)
        negative_count = sum(1 for word in negative_words if word in body_lower)

        total_sentiment_words = positive_count + negative_count
        sentiment_score = 0.0
        if total_sentiment_words > 0:
            sentiment_score = (positive_count - negative_count) / total_sentiment_words

        return {
            "sentiment_score": round(sentiment_score, 2),
            "pain_points": ",".join(pain_points) if pain_points else None,
            "feature_requests": ",".join(feature_requests) if feature_requests else None
        }

    def _extract_topics(self, text: str) -> List[str]:
        """Extract trending topics from text"""
        # Simple keyword-based topic extraction
        topic_keywords = {
            "AI/Machine Learning": ["ai", "machine learning", "ml", "artificial intelligence", "chatgpt", "gpt"],
            "Blockchain/Crypto": ["blockchain", "crypto", "bitcoin", "ethereum", "nft", "web3"],
            "Remote Work": ["remote", "work from home", "wfh", "zoom", "teams", "slack"],
            "E-commerce": ["shopify", "amazon", "ecommerce", "online store", "dropshipping"],
            "SaaS": ["saas", "software", "subscription", "platform", "app"],
            "FinTech": ["fintech", "banking", "payment", "finance", "trading", "investing"],
            "HealthTech": ["health", "medical", "healthcare", "fitness", "wellness"],
            "EdTech": ["education", "learning", "online course", "teaching", "student"],
            "Productivity": ["productivity", "tools", "automation", "efficiency", "workflow"],
            "Marketing": ["marketing", "social media", "ads", "content", "seo"]
        }

        found_topics = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in text for keyword in keywords):
                found_topics.append(topic)

        return found_topics[:5]  # Limit to top 5 topics

    def _identify_market_signals(self, text: str, score: int) -> List[str]:
        """Identify market signals from post content and engagement"""
        signals = []

        # High engagement signal
        if score > 1000:
            signals.append("high_engagement")

        # Pain point signals
        if any(word in text for word in ["problem", "issue", "frustrating", "hate"]):
            signals.append("pain_point_identified")

        # Solution seeking signals
        if any(word in text for word in ["looking for", "need", "recommendation", "suggestion"]):
            signals.append("solution_seeking")

        # Market opportunity signals
        if any(word in text for word in ["business", "startup", "opportunity", "market"]):
            signals.append("business_opportunity")

        return signals

    def _calculate_engagement_rate(self, subreddit) -> float:
        """Calculate engagement rate for subreddit"""
        try:
            if subreddit.subscribers and subreddit.active_user_count:
                return round((subreddit.active_user_count / subreddit.subscribers) * 100, 2)
        except:
            pass
        return 0.0

    def _analyze_growth_trend(self, subreddit) -> str:
        """Analyze growth trend (simplified - would need historical data in production)"""
        # This is a placeholder - in production you'd analyze subscriber growth over time
        if subreddit.subscribers > 1000000:
            return "high_growth"
        elif subreddit.subscribers > 100000:
            return "moderate_growth"
        else:
            return "stable"