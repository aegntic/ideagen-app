"""
Google Trends Connector Configuration
Manages API credentials and connector settings
"""

import os
from typing import Dict, Any, List
from pydantic import BaseSettings, Field


class TrendsConfig(BaseSettings):
    """Google Trends configuration settings"""

    # Google Trends Configuration
    timezone: int = Field(default=240, env="TRENDS_TIMEZONE")  # US Eastern Time
    geo: str = Field(default="US", env="TRENDS_GEO")  # United States
    language: str = Field(default="en-US", env="TRENDS_LANGUAGE")

    # Connector Configuration
    categories: List[str] = Field(
        default=[
            "Artificial Intelligence",
            "Machine Learning",
            "Automation",
            "Productivity Tools",
            "SaaS",
            "FinTech",
            "HealthTech",
            "E-commerce",
            "Remote Work",
            "Sustainability"
        ],
        env="TRENDS_CATEGORIES"
    )
    keywords_limit: int = Field(default=100, env="TRENDS_KEYWORDS_LIMIT")
    timeframe_days: int = Field(default=90, env="TRENDS_TIMEFRAME_DAYS")
    related_queries_limit: int = Field(default=50, env="TRENDS_RELATED_QUERIES_LIMIT")

    # Trending Topics Configuration
    trending_topics_limit: int = Field(default=20, env="TRENDS_TOPICS_LIMIT")
    regions: List[str] = Field(
        default=["US", "CA", "GB", "AU", "DE"],
        env="TRENDS_REGIONS"
    )

    # Fivetran Configuration
    fivetran_api_key: str = Field(..., env="FIVETRAN_API_KEY")
    fivetran_api_secret: str = Field(..., env="FIVETRAN_API_SECRET")
    destination_schema: str = Field(default="trends_data", env="TRENDS_DESTINATION_SCHEMA")

    # Sync Configuration
    sync_frequency_hours: int = Field(default=6, env="TRENDS_SYNC_FREQUENCY")
    batch_size: int = Field(default=200, env="TRENDS_BATCH_SIZE")

    # Retry Configuration
    max_retries: int = Field(default=3, env="TRENDS_MAX_RETRIES")
    retry_delay_seconds: int = Field(default=300, env="TRENDS_RETRY_DELAY")  # 5 minutes

    class Config:
        env_file = ".env"
        case_sensitive = False


def get_config() -> TrendsConfig:
    """Load and return Google Trends configuration"""
    return TrendsConfig()


# Data schema mappings for Fivetran
TREND_SCHEMA = {
    "id": "VARCHAR(255)",
    "keyword": "VARCHAR(255)",
    "interest_level": "INTEGER",
    "is_breakout": "BOOLEAN",
    "source": "VARCHAR(100)",
    "date": "DATE",
    "region": "VARCHAR(10)",
    "category": "VARCHAR(100)",
    "extracted_at": "TIMESTAMP",
    "trend_score": "DECIMAL(5,2)",
    "growth_rate": "DECIMAL(5,2)",
    "volatility": "DECIMAL(3,2)",
    "idea_potential": "DECIMAL(3,2)"
}

RELATED_QUERY_SCHEMA = {
    "id": "VARCHAR(255)",
    "parent_keyword": "VARCHAR(255)",
    "query": "VARCHAR(255)",
    "relation_type": "VARCHAR(50)",
    "interest_level": "INTEGER",
    "extracted_at": "TIMESTAMP",
    "opportunity_score": "DECIMAL(3,2)",
    "market_demand": "VARCHAR(50)",
    "competition_level": "VARCHAR(50)"
}

TRENDING_TOPIC_SCHEMA = {
    "id": "VARCHAR(255)",
    "title": "TEXT",
    "traffic": "VARCHAR(50)",
    "related_articles": "TEXT",
    "picture_url": "TEXT",
    "source": "VARCHAR(100)",
    "date": "DATE",
    "region": "VARCHAR(10)",
    "extracted_at": "TIMESTAMP",
    "topic_score": "DECIMAL(5,2)",
    "category_tags": "TEXT",
    "business_opportunity": "TEXT"
}

REGION_TREND_SCHEMA = {
    "id": "VARCHAR(255)",
    "region": "VARCHAR(10)",
    "keyword": "VARCHAR(255)",
    "interest_level": "INTEGER",
    "date": "DATE",
    "extracted_at": "TIMESTAMP",
    "regional_score": "DECIMAL(5,2)",
    "market_maturity": "VARCHAR(50)",
    "localization_opportunity": "BOOLEAN"
}

CATEGORY_TREND_SCHEMA = {
    "id": "VARCHAR(255)",
    "category": "VARCHAR(100)",
    "keyword": "VARCHAR(255)",
    "interest_level": "INTEGER",
    "date": "DATE",
    "timeframe": "VARCHAR(50)",
    "extracted_at": "TIMESTAMP",
    "category_growth": "DECIMAL(5,2)",
    "market_size_estimate": "TEXT",
    "innovation_potential": "DECIMAL(3,2)"
}