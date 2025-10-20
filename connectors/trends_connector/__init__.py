"""
Google Trends Connector for Fivetran
Production-ready connector for extracting Google Trends data for idea generation
"""

__version__ = "1.0.0"
__author__ = "IdeaGen Team"
__email__ = "team@ideagen.ai"

from .trends_client import TrendsClient
from .connector import TrendsConnector

__all__ = ["TrendsClient", "TrendsConnector"]