"""
GitHub Connector Configuration
Manages API credentials and connector settings
"""

import os
from typing import Dict, Any, List
from pydantic import BaseSettings, Field


class GitHubConfig(BaseSettings):
    """GitHub API configuration settings"""

    # GitHub API Credentials
    token: str = Field(..., env="GITHUB_TOKEN")
    username: str = Field(default="", env="GITHUB_USERNAME")

    # Connector Configuration
    repositories_limit: int = Field(default=100, env="GITHUB_REPOS_LIMIT")
    issues_limit: int = Field(default=50, env="GITHUB_ISSUES_LIMIT")
    commits_limit: int = Field(default=30, env="GITHUB_COMMITS_LIMIT")
    days_back: int = Field(default=30, env="GITHUB_DAYS_BACK")

    # Search Configuration
    languages: List[str] = Field(
        default=["Python", "JavaScript", "TypeScript", "Go", "Rust", "Java"],
        env="GITHUB_LANGUAGES"
    )
    topics: List[str] = Field(
        default=["artificial-intelligence", "machine-learning", "productivity", "automation", "saas"],
        env="GITHUB_TOPICS"
    )
    min_stars: int = Field(default=50, env="GITHUB_MIN_STARS")
    min_forks: int = Field(default=10, env="GITHUB_MIN_FORKS")

    # Repository Analysis
    include_private: bool = Field(default=False, env="GITHUB_INCLUDE_PRIVATE")
    analyze_readme: bool = Field(default=True, env="GITHUB_ANALYZE_README")
    analyze_code: bool = Field(default=False, env="GITHUB_ANALYZE_CODE")

    # Fivetran Configuration
    fivetran_api_key: str = Field(..., env="FIVETRAN_API_KEY")
    fivetran_api_secret: str = Field(..., env="FIVETRAN_API_SECRET")
    destination_schema: str = Field(default="github_data", env="GITHUB_DESTINATION_SCHEMA")

    # Sync Configuration
    sync_frequency_hours: int = Field(default=4, env="GITHUB_SYNC_FREQUENCY")
    batch_size: int = Field(default=100, env="GITHUB_BATCH_SIZE")

    # Retry Configuration
    max_retries: int = Field(default=3, env="GITHUB_MAX_RETRIES")
    retry_delay_seconds: int = Field(default=60, env="GITHUB_RETRY_DELAY")

    class Config:
        env_file = ".env"
        case_sensitive = False


def get_config() -> GitHubConfig:
    """Load and return GitHub configuration"""
    return GitHubConfig()


# Data schema mappings for Fivetran
REPOSITORY_SCHEMA = {
    "id": "BIGINT",
    "name": "VARCHAR(255)",
    "full_name": "VARCHAR(255)",
    "description": "TEXT",
    "url": "TEXT",
    "html_url": "TEXT",
    "clone_url": "TEXT",
    "ssh_url": "TEXT",
    "language": "VARCHAR(100)",
    "languages": "TEXT",
    "stars": "INTEGER",
    "forks": "INTEGER",
    "watchers": "INTEGER",
    "open_issues": "INTEGER",
    "created_at": "TIMESTAMP",
    "updated_at": "TIMESTAMP",
    "pushed_at": "TIMESTAMP",
    "size": "INTEGER",
    "is_private": "BOOLEAN",
    "is_fork": "BOOLEAN",
    "has_issues": "BOOLEAN",
    "has_projects": "BOOLEAN",
    "has_wiki": "BOOLEAN",
    "has_pages": "BOOLEAN",
    "has_downloads": "BOOLEAN",
    "archived": "BOOLEAN",
    "disabled": "BOOLEAN",
    "license": "VARCHAR(255)",
    "default_branch": "VARCHAR(100)",
    "topics": "TEXT",
    "owner_id": "BIGINT",
    "owner_login": "VARCHAR(255)",
    "owner_type": "VARCHAR(50)",
    "extracted_at": "TIMESTAMP",
    "trend_score": "DECIMAL(5,2)",
    "growth_rate": "DECIMAL(5,2)",
    "innovation_potential": "DECIMAL(3,2)",
    "business_opportunity": "TEXT"
}

ISSUE_SCHEMA = {
    "id": "BIGINT",
    "number": "INTEGER",
    "title": "TEXT",
    "body": "TEXT",
    "state": "VARCHAR(50)",
    "user_id": "BIGINT",
    "user_login": "VARCHAR(255)",
    "assignee_id": "BIGINT",
    "assignee_login": "VARCHAR(255)",
    "repository_id": "BIGINT",
    "repository_name": "VARCHAR(255)",
    "milestone_id": "BIGINT",
    "labels": "TEXT",
    "comments": "INTEGER",
    "reactions": "INTEGER",
    "created_at": "TIMESTAMP",
    "updated_at": "TIMESTAMP",
    "closed_at": "TIMESTAMP",
    "locked": "BOOLEAN",
    "pull_request": "BOOLEAN",
    "draft": "BOOLEAN",
    "extracted_at": "TIMESTAMP",
    "pain_point_score": "DECIMAL(3,2)",
    "feature_request_score": "DECIMAL(3,2)",
    "market_signal": "VARCHAR(100)",
    "business_idea": "TEXT"
}

COMMIT_SCHEMA = {
    "sha": "VARCHAR(255)",
    "message": "TEXT",
    "author_id": "BIGINT",
    "author_name": "VARCHAR(255)",
    "author_email": "VARCHAR(255)",
    "author_date": "TIMESTAMP",
    "committer_id": "BIGINT",
    "committer_name": "VARCHAR(255)",
    "committer_email": "VARCHAR(255)",
    "committer_date": "TIMESTAMP",
    "repository_id": "BIGINT",
    "repository_name": "VARCHAR(255)",
    "additions": "INTEGER",
    "deletions": "INTEGER",
    "changed_files": "INTEGER",
    "url": "TEXT",
    "html_url": "TEXT",
    "extracted_at": "TIMESTAMP",
    "feature_indicators": "TEXT",
    "innovation_signals": "TEXT",
    "development_activity": "VARCHAR(50)"
}

CONTRIBUTOR_SCHEMA = {
    "id": "BIGINT",
    "login": "VARCHAR(255)",
    "name": "VARCHAR(255)",
    "email": "VARCHAR(255)",
    "bio": "TEXT",
    "company": "VARCHAR(255)",
    "location": "VARCHAR(255)",
    "blog": "TEXT",
    "followers": "INTEGER",
    "following": "INTEGER",
    "public_repos": "INTEGER",
    "public_gists": "INTEGER",
    "created_at": "TIMESTAMP",
    "updated_at": "TIMESTAMP",
    "type": "VARCHAR(50)",
    "site_admin": "BOOLEAN",
    "extracted_at": "TIMESTAMP",
    "expertise_score": "DECIMAL(3,2)",
    "innovation_index": "DECIMAL(3,2)",
    "technical_skills": "TEXT"
}

ORGANIZATION_SCHEMA = {
    "id": "BIGINT",
    "login": "VARCHAR(255)",
    "name": "VARCHAR(255)",
    "email": "VARCHAR(255)",
    "company": "VARCHAR(255)",
    "location": "VARCHAR(255)",
    "blog": "TEXT",
    "description": "TEXT",
    "followers": "INTEGER",
    "following": "INTEGER",
    "public_repos": "INTEGER",
    "created_at": "TIMESTAMP",
    "updated_at": "TIMESTAMP",
    "type": "VARCHAR(50)",
    "has_organization_projects": "BOOLEAN",
    "has_repository_projects": "BOOLEAN",
    "is_verified": "BOOLEAN",
    "extracted_at": "TIMESTAMP",
    "innovation_leadership": "DECIMAL(3,2)",
    "market_influence": "DECIMAL(3,2)",
    "technology_focus": "TEXT"
}