"""
Google Trends API Client
Handles communication with Google Trends data sources
"""

import asyncio
import aiohttp
import logging
import pandas as pd
import requests
from typing import Dict, List, Any, Optional, AsyncGenerator, Tuple
from datetime import datetime, UTC, timedelta
from urllib.parse import quote
import backoff
from tenacity import retry, stop_after_attempt, wait_exponential
from pytrends.request import TrendReq
import time
import random

from .config import get_config


logger = logging.getLogger(__name__)


class TrendsClient:
    """Google Trends client with error handling and retry logic"""

    def __init__(self, config=None):
        self.config = config or get_config()
        self.pytrends = None
        self._initialize_pytrends()

    def _initialize_pytrends(self):
        """Initialize pytrends client"""
        try:
            self.pytrends = TrendReq(
                hl=self.config.language,
                tz=self.config.timezone,
                geo=self.config.geo,
                retries=self.config.max_retries,
                backoff_factor=self.config.retry_delay_seconds
            )
            logger.info("Pytrends client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize pytrends client: {e}")
            raise

    @backoff.on_exception(
        backoff.expo,
        (requests.RequestException, requests.HTTPError, requests.ConnectionError),
        max_tries=3,
        base=300,  # 5 minutes
        max_value=900  # 15 minutes
    )
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=60, max=300)
    )
    def _rate_limited_request(self, func, *args, **kwargs):
        """Execute pytrends request with rate limiting"""
        try:
            # Add random delay to avoid rate limiting
            delay = random.uniform(1, 3)
            time.sleep(delay)

            result = func(*args, **kwargs)

            # Additional delay between requests
            time.sleep(random.uniform(2, 5))

            return result
        except Exception as e:
            logger.warning(f"Request failed, retrying: {e}")
            raise

    async def get_keyword_trends(
        self,
        keywords: List[str],
        timeframe: Optional[str] = None,
        geo: Optional[str] = None,
        category: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch keyword interest trends over time

        Args:
            keywords: List of keywords to analyze
            timeframe: Time period for analysis (default: last 90 days)
            geo: Geographic region (default: from config)
            category: Category for filtering

        Yields:
            Dict containing trend data
        """
        timeframe = timeframe or f"today {self.config.timeframe_days}d"
        geo = geo or self.config.geo
        category = category or None

        try:
            # Process keywords in batches to avoid rate limiting
            batch_size = 5  # Google Trends limit per request
            keyword_batches = [keywords[i:i + batch_size] for i in range(0, len(keywords), batch_size)]

            for batch in keyword_batches:
                try:
                    # Get interest over time data
                    interest_data = self._rate_limited_request(
                        self.pytrends.interest_over_time,
                        batch,
                        timeframe=timeframe,
                        geo=geo,
                        cat=category
                    )

                    if not interest_data.empty:
                        # Process each keyword in the batch
                        for keyword in batch:
                            if keyword in interest_data.columns:
                                await self._process_keyword_trend_data(
                                    interest_data, keyword, timeframe, geo, category
                                )

                except Exception as e:
                    logger.warning(f"Error processing batch {batch}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error fetching keyword trends: {e}")
            raise

    async def _process_keyword_trend_data(
        self,
        data: pd.DataFrame,
        keyword: str,
        timeframe: str,
        geo: str,
        category: Optional[str]
    ):
        """Process trend data for a single keyword"""
        try:
            # Remove isPartial rows
            if 'isPartial' in data.columns:
                data = data[data['isPartial'] != True]

            # Calculate trend metrics
            interest_values = data[keyword].fillna(0)
            latest_value = interest_values.iloc[-1] if not interest_values.empty else 0
            historical_avg = interest_values.mean()
            volatility = interest_values.std()

            # Calculate growth rate (comparing recent vs historical)
            recent_period = min(7, len(interest_values))  # Last 7 periods
            if len(interest_values) > recent_period:
                recent_avg = interest_values.iloc[-recent_period:].mean()
                growth_rate = ((recent_avg - historical_avg) / historical_avg) * 100 if historical_avg > 0 else 0
            else:
                growth_rate = 0

            # Generate trend records for each date
            for index, row in data.iterrows():
                trend_data = {
                    "id": f"{keyword}_{index.strftime('%Y-%m-%d')}_{geo}",
                    "keyword": keyword,
                    "interest_level": int(row[keyword]) if pd.notna(row[keyword]) else 0,
                    "is_breakout": growth_rate > 50 and latest_value > 50,  # Simple breakout detection
                    "source": "google_trends",
                    "date": index.strftime('%Y-%m-%d'),
                    "region": geo,
                    "category": category or "general",
                    "extracted_at": datetime.now(UTC).isoformat(),
                    "trend_score": min(100, int(row[keykey] if pd.notna(row[keyword]) else 0)),
                    "growth_rate": round(growth_rate, 2),
                    "volatility": round(volatility, 2) if not pd.isna(volatility) else 0,
                    "idea_potential": self._calculate_idea_potential(keyword, latest_value, growth_rate, volatility)
                }

                yield trend_data

        except Exception as e:
            logger.warning(f"Error processing trend data for {keyword}: {e}")

    async def get_related_queries(
        self,
        keyword: str,
        timeframe: Optional[str] = None,
        geo: Optional[str] = None,
        limit: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch related queries for a keyword

        Args:
            keyword: Primary keyword to analyze
            timeframe: Time period for analysis
            geo: Geographic region
            limit: Maximum number of related queries to fetch

        Yields:
            Dict containing related query data
        """
        timeframe = timeframe or f"today {self.config.timeframe_days}d"
        geo = geo or self.config.geo
        limit = limit or self.config.related_queries_limit

        try:
            related_data = self._rate_limited_request(
                self.pytrends.related_queries,
                keyword,
                timeframe=timeframe,
                geo=geo
            )

            # Process both rising and top queries
            for query_type in ['rising', 'top']:
                if query_type in related_data and keyword in related_data[query_type]:
                    queries_df = related_data[query_type][keyword]

                    if queries_df is not None and not queries_df.empty:
                        for _, row in queries_df.head(limit).iterrows():
                            related_query_data = {
                                "id": f"{keyword}_{row.get('query', '').replace(' ', '_')}_{query_type}",
                                "parent_keyword": keyword,
                                "query": row.get('query', ''),
                                "relation_type": query_type,
                                "interest_level": row.get('value', 0) if pd.notna(row.get('value')) else 0,
                                "extracted_at": datetime.now(UTC).isoformat(),
                                "opportunity_score": self._calculate_opportunity_score(row, query_type),
                                "market_demand": self._assess_market_demand(row),
                                "competition_level": self._assess_competition_level(row, query_type)
                            }

                            yield related_query_data

        except Exception as e:
            logger.warning(f"Error fetching related queries for {keyword}: {e}")

    async def get_trending_topics(
        self,
        geo: Optional[str] = None,
        limit: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch currently trending topics

        Args:
            geo: Geographic region
            limit: Maximum number of topics to fetch

        Yields:
            Dict containing trending topic data
        """
        geo = geo or self.config.geo
        limit = limit or self.config.trending_topics_limit

        try:
            trending_data = self._rate_limited_request(
                self.pytrends.trending_searches,
                pn=geo
            )

            if trending_data is not None and not trending_data.empty:
                for index, row in trending_data.head(limit).iterrows():
                    topic_data = {
                        "id": f"trending_{index}_{geo}_{datetime.now().strftime('%Y%m%d')}",
                        "title": row.get('title', ''),
                        "traffic": str(row.get('formattedTraffic', '')),
                        "related_articles": str(row.get('related_articles', [])),
                        "picture_url": row.get('picture', ''),
                        "source": "google_trending",
                        "date": datetime.now(UTC).strftime('%Y-%m-%d'),
                        "region": geo,
                        "extracted_at": datetime.now(UTC).isoformat(),
                        "topic_score": self._calculate_topic_score(row),
                        "category_tags": self._extract_category_tags(row.get('title', '')),
                        "business_opportunity": self._assess_business_opportunity(row.get('title', ''))
                    }

                    yield topic_data

        except Exception as e:
            logger.warning(f"Error fetching trending topics for {geo}: {e}")

    async def get_regional_trends(
        self,
        keyword: str,
        timeframe: Optional[str] = None,
        regions: Optional[List[str]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch regional interest data for a keyword

        Args:
            keyword: Keyword to analyze
            timeframe: Time period for analysis
            regions: List of regions to analyze

        Yields:
            Dict containing regional trend data
        """
        timeframe = timeframe or f"today {self.config.timeframe_days}d"
        regions = regions or self.config.regions

        for region in regions:
            try:
                regional_data = self._rate_limited_request(
                    self.pytrends.interest_by_region,
                    [keyword],
                    timeframe=timeframe,
                    geo=region,
                    resolution='COUNTRY'
                )

                if regional_data is not None and not regional_data.empty:
                    for index, row in regional_data.iterrows():
                        regional_trend_data = {
                            "id": f"{keyword}_{index}_{region}_{datetime.now().strftime('%Y%m%d')}",
                            "region": region,
                            "keyword": keyword,
                            "interest_level": int(row[keyword]) if pd.notna(row[keyword]) else 0,
                            "date": datetime.now(UTC).strftime('%Y-%m-%d'),
                            "extracted_at": datetime.now(UTC).isoformat(),
                            "regional_score": int(row[keyword]) if pd.notna(row[keyword]) else 0,
                            "market_maturity": self._assess_market_maturity(row[keyword]),
                            "localization_opportunity": self._assess_localization_opportunity(keyword, row[keyword])
                        }

                        yield regional_trend_data

            except Exception as e:
                logger.warning(f"Error fetching regional trends for {region}: {e}")
                continue

    async def get_category_trends(
        self,
        category_keywords: List[str],
        category_name: str,
        timeframe: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch trends for specific business categories

        Args:
            category_keywords: List of keywords representing a category
            category_name: Name of the category
            timeframe: Time period for analysis

        Yields:
            Dict containing category trend data
        """
        timeframe = timeframe or f"today {self.config.timeframe_days}d"

        try:
            async for trend_data in self.get_keyword_trends(
                keywords=category_keywords,
                timeframe=timeframe
            ):
                # Enhance trend data with category-specific information
                trend_data.update({
                    "category": category_name,
                    "timeframe": timeframe,
                    "category_growth": trend_data.get("growth_rate", 0),
                    "market_size_estimate": self._estimate_market_size(category_name, trend_data.get("interest_level", 0)),
                    "innovation_potential": self._assess_innovation_potential(trend_data)
                })

                yield trend_data

        except Exception as e:
            logger.warning(f"Error fetching category trends for {category_name}: {e}")

    def _calculate_idea_potential(
        self,
        keyword: str,
        current_interest: int,
        growth_rate: float,
        volatility: float
    ) -> float:
        """Calculate idea generation potential score (0-1)"""
        try:
            # Base score from current interest
            interest_score = min(1.0, current_interest / 100.0)

            # Growth bonus
            growth_score = min(1.0, max(0, growth_rate / 100.0))

            # Volatility penalty (high volatility = risk)
            volatility_penalty = min(0.5, volatility / 50.0)

            # Keyword relevance (check for business/tech keywords)
            business_keywords = [
                'app', 'software', 'platform', 'tool', 'service', 'api',
                'ai', 'automation', 'productivity', 'solution', 'technology'
            ]
            relevance_score = 0.5  # Base relevance
            for b_keyword in business_keywords:
                if b_keyword in keyword.lower():
                    relevance_score += 0.1

            # Calculate final score
            potential = (interest_score * 0.3 +
                        growth_score * 0.4 +
                        relevance_score * 0.3 -
                        volatility_penalty * 0.2)

            return round(max(0, min(1.0, potential)), 2)

        except Exception:
            return 0.5  # Default score

    def _calculate_opportunity_score(self, query_row: pd.Series, query_type: str) -> float:
        """Calculate opportunity score for related queries"""
        try:
            base_score = 0.5

            # Rising queries get higher base score
            if query_type == 'rising':
                base_score = 0.7

            # Extract value if available
            value = query_row.get('value', 0)
            if pd.notna(value) and value != '<1':
                value_score = min(1.0, float(str(value).replace('+', '').replace('%', '')) / 100.0)
                base_score += value_score * 0.3

            return round(min(1.0, base_score), 2)

        except Exception:
            return 0.5

    def _assess_market_demand(self, query_row: pd.Series) -> str:
        """Assess market demand level"""
        try:
            value = query_row.get('value', 0)
            if pd.notna(value):
                value_str = str(value)
                if '+' in value_str or '%' in value_str:
                    num_value = float(value_str.replace('+', '').replace('%', ''))
                    if num_value > 100:
                        return "high"
                    elif num_value > 50:
                        return "medium"
                    else:
                        return "low"
            return "unknown"

        except Exception:
            return "unknown"

    def _assess_competition_level(self, query_row: pd.Series, query_type: str) -> str:
        """Assess competition level"""
        try:
            # Rising queries might have lower competition
            if query_type == 'rising':
                return "low_to_medium"
            else:
                # Top queries might have higher competition
                return "medium_to_high"

        except Exception:
            return "unknown"

    def _calculate_topic_score(self, topic_row: pd.Series) -> float:
        """Calculate score for trending topics"""
        try:
            title = topic_row.get('title', '')
            traffic = topic_row.get('formattedTraffic', '')

            # Base score from traffic
            if traffic and '+' in traffic:
                traffic_num = float(traffic.replace('+', '').replace('K', '000').replace('M', '000000'))
                base_score = min(1.0, traffic_num / 1000000.0)  # Normalize to 1M+
            else:
                base_score = 0.5

            # Boost for relevant keywords
            relevant_keywords = ['app', 'software', 'technology', 'startup', 'business', 'ai', 'tool']
            for keyword in relevant_keywords:
                if keyword.lower() in title.lower():
                    base_score += 0.1

            return round(min(1.0, base_score), 2)

        except Exception:
            return 0.5

    def _extract_category_tags(self, title: str) -> str:
        """Extract category tags from title"""
        tags = []
        title_lower = title.lower()

        category_mapping = {
            'ai': ['ai', 'artificial intelligence', 'machine learning'],
            'productivity': ['productivity', 'tool', 'app', 'software'],
            'business': ['business', 'startup', 'company', 'service'],
            'technology': ['technology', 'tech', 'digital'],
            'social': ['social', 'media', 'network', 'community'],
            'health': ['health', 'medical', 'fitness', 'wellness'],
            'finance': ['finance', 'fintech', 'money', 'payment'],
            'entertainment': ['game', 'movie', 'music', 'video']
        }

        for category, keywords in category_mapping.items():
            if any(keyword in title_lower for keyword in keywords):
                tags.append(category)

        return ','.join(tags) if tags else 'general'

    def _assess_business_opportunity(self, title: str) -> str:
        """Assess business opportunity level"""
        title_lower = title.lower()

        opportunity_keywords = [
            ('launch', 'new_product'),
            ('update', 'product_improvement'),
            ('feature', 'feature_expansion'),
            ('partnership', 'collaboration_opportunity'),
            ('acquisition', 'market_consolidation'),
            ('funding', 'investment_opportunity')
        ]

        for keyword, opportunity in opportunity_keywords:
            if keyword in title_lower:
                return opportunity

        return 'market_trend'

    def _assess_market_maturity(self, interest_level) -> str:
        """Assess market maturity based on interest level"""
        try:
            if pd.notna(interest_level):
                level = int(interest_level)
                if level > 80:
                    return "mature"
                elif level > 40:
                    return "growing"
                else:
                    return "emerging"
            return "unknown"

        except Exception:
            return "unknown"

    def _assess_localization_opportunity(self, keyword: str, interest_level) -> bool:
        """Assess if there's localization opportunity"""
        try:
            if pd.notna(interest_level):
                # Low to medium interest in a region might indicate localization opportunity
                level = int(interest_level)
                return 20 <= level <= 60
            return False

        except Exception:
            return False

    def _estimate_market_size(self, category: str, interest_level: int) -> str:
        """Estimate market size based on category and interest level"""
        try:
            if pd.notna(interest_level):
                level = int(interest_level)

                # Simple market size estimation
                if level > 80:
                    return "large_market"
                elif level > 50:
                    return "medium_market"
                elif level > 20:
                    return "small_market"
                else:
                    return "niche_market"

            return "unknown"

        except Exception:
            return "unknown"

    def _assess_innovation_potential(self, trend_data: Dict[str, Any]) -> float:
        """Assess innovation potential of a trend"""
        try:
            growth_rate = trend_data.get("growth_rate", 0)
            volatility = trend_data.get("volatility", 0)
            idea_potential = trend_data.get("idea_potential", 0)

            # High growth and moderate volatility might indicate innovation opportunities
            innovation_score = (min(1.0, max(0, growth_rate / 100.0)) * 0.5 +
                              min(1.0, volatility / 50.0) * 0.3 +
                              idea_potential * 0.2)

            return round(innovation_score, 2)

        except Exception:
            return 0.5