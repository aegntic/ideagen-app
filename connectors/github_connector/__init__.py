"""
GitHub Connector for Fivetran
Production-ready connector for extracting GitHub data for idea generation
"""

__version__ = "1.0.0"
__author__ = "IdeaGen Team"
__email__ = "team@ideagen.ai"

from .github_client import GitHubClient
from .connector import GitHubConnector

__all__ = ["GitHubClient", "GitHubConnector"]