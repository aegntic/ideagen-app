"""
Reddit Connector for Fivetran
Production-ready connector for extracting Reddit data for idea generation
"""

__version__ = "1.0.0"
__author__ = "IdeaGen Team"
__email__ = "team@ideagen.ai"

from .reddit_client import RedditClient
from .connector import RedditConnector

__all__ = ["RedditClient", "RedditConnector"]