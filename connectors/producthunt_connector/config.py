"""
Product Hunt Connector Configuration
Manages API credentials and connector settings
"""

import os
from typing import Dict, Any, List
from pydantic import BaseSettings, Field


class ProductHuntConfig(BaseSettings):
    """Product Hunt API configuration settings"""

    # Product Hunt API Credentials
    api_key: str = Field(..., env="PRODUCTHUNT_API_KEY")
    api_secret: str = Field(..., env="PRODUCTHUNT_API_SECRET")
   _developer_token: str = Field(default="", env="PRODUCTHUNT_DEVELOPER_TOKEN")

    # Connector Configuration
    posts_limit: int = Field(default=50, env="PRODUCTHUNT_POSTS_LIMIT")
    comments_limit: int = Field(default=20, env="PRODUCTHUNT_COMMENTS_LIMIT")
    categories: List[str] = Field(
        default=["tech", "productivity", "design", "marketing", "developer-tools"],
        env="PRODUCTHUNT_CATEGORIES"
    )
    days_back: int = Field(default=7, env="PRODUCTHUNT_DAYS_BACK")

    # Fivetran Configuration
    fivetran_api_key: str = Field(..., env="FIVETRAN_API_KEY")
    fivetran_api_secret: str = Field(..., env="FIVETRAN_API_SECRET")
    destination_schema: str = Field(default="producthunt_data", env="PRODUCTHUNT_DESTINATION_SCHEMA")

    # Sync Configuration
    sync_frequency_minutes: int = Field(default=120, env="PRODUCTHUNT_SYNC_FREQUENCY")
    batch_size: int = Field(default=500, env="PRODUCTHUNT_BATCH_SIZE")

    # Retry Configuration
    max_retries: int = Field(default=3, env="PRODUCTHUNT_MAX_RETRIES")
    retry_delay_seconds: int = Field(default=60, env="PRODUCTHUNT_RETRY_DELAY")

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def developer_token(self) -> str:
        """Get developer token from API key and secret"""
        if self._developer_token:
            return self._developer_token

        # In production, this would be obtained via OAuth flow
        # For now, use the API key as a fallback
        return f"Bearer {self.api_key}"


def get_config() -> ProductHuntConfig:
    """Load and return Product Hunt configuration"""
    return ProductHuntConfig()


# Data schema mappings for Fivetran
PRODUCT_SCHEMA = {
    "id": "VARCHAR(255)",
    "name": "TEXT",
    "tagline": "TEXT",
    "description": "TEXT",
    "slug": "VARCHAR(255)",
    "url": "TEXT",
    "website": "TEXT",
    "votes_count": "INTEGER",
    "comments_count": "INTEGER",
    "featured_at": "TIMESTAMP",
    "created_at": "TIMESTAMP",
    "day": "DATE",
    "category_id": "INTEGER",
    "topic_ids": "TEXT",
    "user_id": "INTEGER",
    "maker_id": "INTEGER",
    "redirect_url": "TEXT",
    "screenshot_url": "TEXT",
    "thumbnail_url": "TEXT",
    "reviews_count": "INTEGER",
    "current_user_reviewed": "BOOLEAN",
    "product_state": "VARCHAR(50)",
    "ios_url": "TEXT",
    "android_url": "TEXT",
    "web_url": "TEXT",
    "extracted_at": "TIMESTAMP",
    "idea_generation_score": "DECIMAL(3,2)",
    "market_validation": "TEXT",
    "trend_signals": "TEXT",
    "competition_analysis": "TEXT"
}

MAKER_SCHEMA = {
    "id": "INTEGER",
    "name": "VARCHAR(255)",
    "username": "VARCHAR(255)",
    "url": "TEXT",
    "headline": "TEXT",
    "bio": "TEXT",
    "twitter_username": "VARCHAR(255)",
    "website_url": "TEXT",
    "profile_image": "TEXT",
    "followers_count": "INTEGER",
    "followees_count": "INTEGER",
    "posts_count": "INTEGER",
    "collections_count": "INTEGER",
    "comments_count": "INTEGER",
    "extracted_at": "TIMESTAMP",
    "maker_score": "DECIMAL(3,2)",
    "expertise_areas": "TEXT"
}

COMMENT_SCHEMA = {
    "id": "INTEGER",
    "body": "TEXT",
    "created_at": "TIMESTAMP",
    "user_id": "INTEGER",
    "post_id": "INTEGER",
    "parent_id": "INTEGER",
    "child_comments_count": "INTEGER",
    "votes_count": "INTEGER",
    "truncated": "BOOLEAN",
    "deleted": "BOOLEAN",
    "extracted_at": "TIMESTAMP",
    "sentiment_score": "DECIMAL(3,2)",
    "feedback_type": "VARCHAR(100)",
    "feature_requests": "TEXT",
    "pain_points": "TEXT",
    "market_insights": "TEXT"
}

CATEGORY_SCHEMA = {
    "id": "INTEGER",
    "name": "VARCHAR(255)",
    "slug": "VARCHAR(255)",
    "description": "TEXT",
    "color": "VARCHAR(10)",
    "featured": "BOOLEAN",
    "position": "INTEGER",
    "api_slug": "VARCHAR(255)",
    "extracted_at": "TIMESTAMP",
    "trend_score": "DECIMAL(5,2)",
    "market_opportunity": "TEXT"
}