"""
Product Hunt Connector for Fivetran
Production-ready connector for extracting Product Hunt data for idea generation
"""

__version__ = "1.0.0"
__author__ = "IdeaGen Team"
__email__ = "team@ideagen.ai"

from .producthunt_client import ProductHuntClient
from .connector import ProductHuntConnector

__all__ = ["ProductHuntClient", "ProductHuntConnector"]