"""
Reddit Connector Configuration
Manages API credentials and connector settings
"""

import os
from typing import Dict, Any, List
from pydantic import BaseSettings, Field


class RedditConfig(BaseSettings):
    """Reddit API configuration settings"""

    # Reddit API Credentials
    client_id: str = Field(..., env="REDDIT_CLIENT_ID")
    client_secret: str = Field(..., env="REDDIT_CLIENT_SECRET")
    user_agent: str = Field(default="IdeaGen-Reddit-Connector/1.0", env="REDDIT_USER_AGENT")

    # Connector Configuration
    subreddits: List[str] = Field(
        default=["Entrepreneur", "startups", "SaaS", "SideProject", "IndieHackers"],
        env="REDDIT_SUBREDDITS"
    )
    post_limit: int = Field(default=100, env="REDDIT_POST_LIMIT")
    comment_limit: int = Field(default=50, env="REDDIT_COMMENT_LIMIT")
    time_filter: str = Field(default="week", env="REDDIT_TIME_FILTER")  # hour, day, week, month, year, all

    # Fivetran Configuration
    fivetran_api_key: str = Field(..., env="FIVETRAN_API_KEY")
    fivetran_api_secret: str = Field(..., env="FIVETRAN_API_SECRET")
    destination_schema: str = Field(default="reddit_data", env="REDDIT_DESTINATION_SCHEMA")

    # Sync Configuration
    sync_frequency_minutes: int = Field(default=60, env="REDDIT_SYNC_FREQUENCY")
    batch_size: int = Field(default=1000, env="REDDIT_BATCH_SIZE")

    # Retry Configuration
    max_retries: int = Field(default=3, env="REDDIT_MAX_RETRIES")
    retry_delay_seconds: int = Field(default=60, env="REDDIT_RETRY_DELAY")

    class Config:
        env_file = ".env"
        case_sensitive = False


def get_config() -> RedditConfig:
    """Load and return Reddit configuration"""
    return RedditConfig()


# Data schema mappings for Fivetran
POST_SCHEMA = {
    "id": "VARCHAR(255)",
    "title": "TEXT",
    "author": "VARCHAR(255)",
    "subreddit": "VARCHAR(255)",
    "score": "INTEGER",
    "num_comments": "INTEGER",
    "upvote_ratio": "DECIMAL(3,2)",
    "created_utc": "TIMESTAMP",
    "url": "TEXT",
    "selftext": "TEXT",
    "permalink": "TEXT",
    "is_self": "BOOLEAN",
    "over_18": "BOOLEAN",
    "spoiler": "BOOLEAN",
    "stickied": "BOOLEAN",
    "distinguished": "VARCHAR(50)",
    "flair_text": "VARCHAR(255)",
    "awards": "INTEGER",
    "post_hint": "VARCHAR(100)",
    "domain": "VARCHAR(255)",
    "extracted_at": "TIMESTAMP",
    "idea_generation_score": "DECIMAL(3,2)",
    "trending_topics": "TEXT",
    "market_signals": "TEXT"
}

COMMENT_SCHEMA = {
    "id": "VARCHAR(255)",
    "post_id": "VARCHAR(255)",
    "author": "VARCHAR(255)",
    "body": "TEXT",
    "score": "INTEGER",
    "created_utc": "TIMESTAMP",
    "permalink": "TEXT",
    "is_submitter": "BOOLEAN",
    "distinguished": "VARCHAR(50)",
    "stickied": "BOOLEAN",
    "replies": "INTEGER",
    "depth": "INTEGER",
    "extracted_at": "TIMESTAMP",
    "sentiment_score": "DECIMAL(3,2)",
    "pain_points": "TEXT",
    "feature_requests": "TEXT"
}

SUBREDDIT_SCHEMA = {
    "name": "VARCHAR(255)",
    "title": "TEXT",
    "description": "TEXT",
    "subscribers": "INTEGER",
    "active_users": "INTEGER",
    "created_utc": "TIMESTAMP",
    "public_description": "TEXT",
    "icon_img": "TEXT",
    "banner_img": "TEXT",
    "over18": "BOOLEAN",
    "advertiser_category": "VARCHAR(100)",
    "extracted_at": "TIMESTAMP",
    "engagement_rate": "DECIMAL(5,2)",
    "growth_trend": "VARCHAR(50)"
}