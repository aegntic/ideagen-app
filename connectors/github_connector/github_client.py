"""
GitHub API Client
Handles communication with GitHub API
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator, Tuple
from datetime import datetime, UTC, timedelta
import backoff
from tenacity import retry, stop_after_attempt, wait_exponential
from github import Github
from github.GithubException import GithubException, RateLimitExceededException, UnknownObjectException

from .config import get_config


logger = logging.getLogger(__name__)


class GitHubClient:
    """GitHub API client with error handling and retry logic"""

    def __init__(self, config=None):
        self.config = config or get_config()
        self.github = None
        self._initialize_github()

    def _initialize_github(self):
        """Initialize GitHub client"""
        try:
            self.github = Github(
                self.config.token,
                per_page=100,  # Max per page
                retry=self.config.max_retries,
                timeout=30
            )
            # Test authentication
            user = self.github.get_user()
            logger.info(f"Connected to GitHub as: {user.login}")
        except Exception as e:
            logger.error(f"Failed to initialize GitHub client: {e}")
            raise

    @backoff.on_exception(
        backoff.expo,
        (RateLimitExceededException, GithubException),
        max_tries=3,
        base=60,
        max_value=300
    )
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _rate_limited_github_call(self, func, *args, **kwargs):
        """Execute GitHub API call with rate limiting"""
        try:
            return func(*args, **kwargs)
        except RateLimitExceededException as e:
            # Get reset time and wait
            reset_time = e.data.get('reset', 0)
            current_time = datetime.now(UTC).timestamp()
            wait_time = max(reset_time - current_time, 60)
            logger.warning(f"Rate limit hit, waiting {wait_time} seconds")
            raise
        except GithubException as e:
            logger.warning(f"GitHub API error: {e}")
            raise

    async def get_trending_repositories(
        self,
        languages: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        min_stars: Optional[int] = None,
        days_back: Optional[int] = None,
        limit: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch trending repositories

        Args:
            languages: List of programming languages to filter by
            topics: List of topics to filter by
            min_stars: Minimum number of stars
            days_back: Number of days to look back
            limit: Maximum number of repositories to fetch

        Yields:
            Dict containing repository data
        """
        languages = languages or self.config.languages
        topics = topics or self.config.topics
        min_stars = min_stars or self.config.min_stars
        days_back = days_back or self.config.days_back
        limit = limit or self.config.repositories_limit

        try:
            # Build search query
            query_parts = []

            # Add date filter
            created_date = (datetime.now(UTC) - timedelta(days=days_back)).strftime("%Y-%m-%d")
            query_parts.append(f"created:>{created_date}")

            # Add language filter
            if languages:
                language_query = " ".join([f"language:{lang}" for lang in languages[:3]])  # Limit to 3 languages
                query_parts.append(f"({language_query})")

            # Add topic filter
            if topics:
                topic_query = " ".join([f"topic:{topic}" for topic in topics[:3]])  # Limit to 3 topics
                query_parts.append(f"({topic_query})")

            # Add stars filter
            query_parts.append(f"stars:>{min_stars}")

            # Exclude forks to focus on original projects
            query_parts.append("fork:false")

            # Combine query parts
            search_query = " ".join(query_parts)

            logger.info(f"Searching repositories with query: {search_query}")

            try:
                # Search repositories
                repos = self._rate_limited_github_call(
                    self.github.search_repositories,
                    query=search_query,
                    sort="stars",
                    order="desc"
                )

                repo_count = 0
                for repo in repos:
                    if repo_count >= limit:
                        break

                    try:
                        # Transform and enhance repository data
                        repo_data = self._transform_repository_data(repo)

                        # Add trend analysis
                        repo_data.update(self._analyze_repository_trends(repo))

                        yield repo_data
                        repo_count += 1

                    except Exception as e:
                        logger.warning(f"Error processing repository {repo.full_name}: {e}")
                        continue

            except UnknownObjectException as e:
                logger.warning(f"Search failed - no results found: {e}")
                return

        except Exception as e:
            logger.error(f"Error fetching trending repositories: {e}")
            raise

    async def get_repository_issues(
        self,
        repo_full_name: str,
        state: str = "open",
        limit: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch issues for a specific repository

        Args:
            repo_full_name: Full repository name (owner/repo)
            state: Issue state (open, closed, all)
            limit: Maximum number of issues to fetch

        Yields:
            Dict containing issue data
        """
        limit = limit or self.config.issues_limit

        try:
            repo = self._rate_limited_github_call(
                self.github.get_repo,
                repo_full_name
            )

            issues = self._rate_limited_github_call(
                repo.get_issues,
                state=state,
                sort="created",
                direction="desc"
            )

            issue_count = 0
            for issue in issues:
                if issue_count >= limit:
                    break

                try:
                    # Skip pull requests if focusing on issues
                    if issue.pull_request:
                        continue

                    # Transform and analyze issue data
                    issue_data = self._transform_issue_data(issue, repo)

                    # Add business opportunity analysis
                    issue_data.update(self._analyze_issue_for_opportunities(issue))

                    yield issue_data
                    issue_count += 1

                except Exception as e:
                    logger.warning(f"Error processing issue {issue.number}: {e}")
                    continue

        except UnknownObjectException:
            logger.warning(f"Repository {repo_full_name} not found")
        except Exception as e:
            logger.error(f"Error fetching issues for {repo_full_name}: {e}")

    async def get_repository_commits(
        self,
        repo_full_name: str,
        days_back: Optional[int] = None,
        limit: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch recent commits for a specific repository

        Args:
            repo_full_name: Full repository name (owner/repo)
            days_back: Number of days to look back
            limit: Maximum number of commits to fetch

        Yields:
            Dict containing commit data
        """
        days_back = days_back or self.config.days_back
        limit = limit or self.config.commits_limit

        try:
            repo = self._rate_limited_github_call(
                self.github.get_repo,
                repo_full_name
            )

            # Get commits since specified date
            since_date = datetime.now(UTC) - timedelta(days=days_back)
            commits = self._rate_limited_github_call(
                repo.get_commits,
                since=since_date,
                order="desc"
            )

            commit_count = 0
            for commit in commits:
                if commit_count >= limit:
                    break

                try:
                    # Transform and analyze commit data
                    commit_data = self._transform_commit_data(commit, repo)

                    # Add feature indicators
                    commit_data.update(self._analyze_commit_for_features(commit))

                    yield commit_data
                    commit_count += 1

                except Exception as e:
                    logger.warning(f"Error processing commit {commit.sha[:8]}: {e}")
                    continue

        except UnknownObjectException:
            logger.warning(f"Repository {repo_full_name} not found")
        except Exception as e:
            logger.error(f"Error fetching commits for {repo_full_name}: {e}")

    async def get_contributor_data(
        self,
        repo_full_name: str,
        limit: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch contributor data for a specific repository

        Args:
            repo_full_name: Full repository name (owner/repo)
            limit: Maximum number of contributors to fetch

        Yields:
            Dict containing contributor data
        """
        limit = limit or 20  # Limit to top 20 contributors

        try:
            repo = self._rate_limited_github_call(
                self.github.get_repo,
                repo_full_name
            )

            contributors = self._rate_limited_github_call(
                repo.get_contributors
            )

            contributor_count = 0
            for contributor in contributors:
                if contributor_count >= limit:
                    break

                try:
                    # Transform and enhance contributor data
                    contributor_data = self._transform_contributor_data(contributor)

                    # Add expertise analysis
                    contributor_data.update(self._analyze_contributor_expertise(contributor))

                    yield contributor_data
                    contributor_count += 1

                except Exception as e:
                    logger.warning(f"Error processing contributor {contributor.login}: {e}")
                    continue

        except UnknownObjectException:
            logger.warning(f"Repository {repo_full_name} not found")
        except Exception as e:
            logger.error(f"Error fetching contributors for {repo_full_name}: {e}")

    def _transform_repository_data(self, repo) -> Dict[str, Any]:
        """Transform GitHub repository data to standardized format"""
        try:
            # Get languages
            languages = {}
            try:
                languages = self._rate_limited_github_call(repo.get_languages)
            except:
                languages = {}

            # Get topics
            topics = repo.get_topics()

            # Get license
            license_name = None
            if repo.license:
                license_name = repo.license.name

            return {
                "id": repo.id,
                "name": repo.name,
                "full_name": repo.full_name,
                "description": repo.description,
                "url": repo.url,
                "html_url": repo.html_url,
                "clone_url": repo.clone_url,
                "ssh_url": repo.ssh_url,
                "language": repo.language,
                "languages": ",".join(languages.keys()) if languages else None,
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "watchers": repo.watchers_count,
                "open_issues": repo.open_issues_count,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
                "size": repo.size,
                "is_private": repo.private,
                "is_fork": repo.fork,
                "has_issues": repo.has_issues,
                "has_projects": repo.has_projects,
                "has_wiki": repo.has_wiki,
                "has_pages": repo.has_pages,
                "has_downloads": repo.has_downloads,
                "archived": repo.archived,
                "disabled": repo.disabled,
                "license": license_name,
                "default_branch": repo.default_branch,
                "topics": ",".join(topics) if topics else None,
                "owner_id": repo.owner.id,
                "owner_login": repo.owner.login,
                "owner_type": repo.owner.type,
                "extracted_at": datetime.now(UTC).isoformat()
            }
        except Exception as e:
            logger.warning(f"Error transforming repository data: {e}")
            return {}

    def _transform_issue_data(self, issue, repo) -> Dict[str, Any]:
        """Transform GitHub issue data to standardized format"""
        try:
            # Get labels
            labels = [label.name for label in issue.labels]

            # Get assignee
            assignee_id = assignee_login = None
            if issue.assignee:
                assignee_id = issue.assignee.id
                assignee_login = issue.assignee.login

            # Get milestone
            milestone_id = None
            if issue.milestone:
                milestone_id = issue.milestone.id

            # Get reactions
            reactions = 0
            try:
                reactions = self._rate_limited_github_call(issue.get_reactions).totalCount
            except:
                pass

            return {
                "id": issue.id,
                "number": issue.number,
                "title": issue.title,
                "body": issue.body,
                "state": issue.state,
                "user_id": issue.user.id,
                "user_login": issue.user.login,
                "assignee_id": assignee_id,
                "assignee_login": assignee_login,
                "repository_id": repo.id,
                "repository_name": repo.full_name,
                "milestone_id": milestone_id,
                "labels": ",".join(labels) if labels else None,
                "comments": issue.comments,
                "reactions": reactions,
                "created_at": issue.created_at.isoformat() if issue.created_at else None,
                "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
                "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                "locked": issue.locked,
                "pull_request": issue.pull_request is not None,
                "draft": getattr(issue, 'draft', False),
                "extracted_at": datetime.now(UTC).isoformat()
            }
        except Exception as e:
            logger.warning(f"Error transforming issue data: {e}")
            return {}

    def _transform_commit_data(self, commit, repo) -> Dict[str, Any]:
        """Transform GitHub commit data to standardized format"""
        try:
            # Get commit stats
            additions = deletions = changed_files = 0
            try:
                if commit.stats:
                    additions = commit.stats.get('additions', 0)
                    deletions = commit.stats.get('deletions', 0)
                    changed_files = commit.stats.get('files', 0)
            except:
                pass

            return {
                "sha": commit.sha,
                "message": commit.commit.message,
                "author_id": commit.author.id if commit.author else None,
                "author_name": commit.commit.author.name,
                "author_email": commit.commit.author.email,
                "author_date": commit.commit.author.date.isoformat() if commit.commit.author.date else None,
                "committer_id": commit.committer.id if commit.committer else None,
                "committer_name": commit.commit.committer.name,
                "committer_email": commit.commit.committer.email,
                "committer_date": commit.commit.committer.date.isoformat() if commit.commit.committer.date else None,
                "repository_id": repo.id,
                "repository_name": repo.full_name,
                "additions": additions,
                "deletions": deletions,
                "changed_files": changed_files,
                "url": commit.url,
                "html_url": commit.html_url,
                "extracted_at": datetime.now(UTC).isoformat()
            }
        except Exception as e:
            logger.warning(f"Error transforming commit data: {e}")
            return {}

    def _transform_contributor_data(self, contributor) -> Dict[str, Any]:
        """Transform GitHub contributor data to standardized format"""
        try:
            # Get additional user details
            name = company = location = blog = bio = ""
            followers = following = public_repos = public_gists = 0
            created_at = updated_at = None
            user_type = "User"
            site_admin = False

            try:
                # Get full user object
                user = self._rate_limited_github_call(self.github.get_user, contributor.login)

                name = user.name or ""
                company = user.company or ""
                location = user.location or ""
                blog = user.blog or ""
                bio = user.bio or ""
                followers = user.followers
                following = user.following
                public_repos = user.public_repos
                public_gists = user.public_gists
                created_at = user.created_at.isoformat() if user.created_at else None
                updated_at = user.updated_at.isoformat() if user.updated_at else None
                user_type = user.type
                site_admin = user.site_admin

            except Exception as e:
                logger.warning(f"Error getting full user data for {contributor.login}: {e}")

            return {
                "id": contributor.id,
                "login": contributor.login,
                "name": name,
                "email": contributor.email or "",
                "bio": bio,
                "company": company,
                "location": location,
                "blog": blog,
                "followers": followers,
                "following": following,
                "public_repos": public_repos,
                "public_gists": public_gists,
                "created_at": created_at,
                "updated_at": updated_at,
                "type": user_type,
                "site_admin": site_admin,
                "extracted_at": datetime.now(UTC).isoformat()
            }
        except Exception as e:
            logger.warning(f"Error transforming contributor data: {e}")
            return {}

    def _analyze_repository_trends(self, repo) -> Dict[str, Any]:
        """Analyze repository for trend indicators"""
        try:
            stars = repo.stargazers_count
            forks = repo.forks_count
            open_issues = repo.open_issues_count
            days_since_created = 1

            if repo.created_at:
                days_since_created = max(1, (datetime.now(UTC) - repo.created_at.replace(tzinfo=None)).days)

            # Calculate growth metrics
            stars_per_day = stars / days_since_created if days_since_created > 0 else 0
            forks_per_day = forks / days_since_created if days_since_created > 0 else 0

            # Calculate trend score
            trend_score = min(100, (stars_per_day * 10) + (forks_per_day * 5))

            # Calculate growth rate (based on recent activity)
            growth_rate = min(100, (stars_per_day * 100))

            # Innovation potential based on topics and language
            innovation_keywords = ["ai", "machine learning", "blockchain", "iot", "ar", "vr", "automation"]
            innovation_potential = 0.5  # Base score

            if repo.description:
                desc_lower = repo.description.lower()
                for keyword in innovation_keywords:
                    if keyword in desc_lower:
                        innovation_potential += 0.1

            topics = repo.get_topics()
            for topic in topics:
                for keyword in innovation_keywords:
                    if keyword in topic.lower():
                        innovation_potential += 0.1

            innovation_potential = min(1.0, innovation_potential)

            # Business opportunity assessment
            business_opportunities = []
            if stars > 1000:
                business_opportunities.append("high_community_interest")
            if forks > 100:
                business_opportunities.append("active_development")
            if open_issues > 50:
                business_opportunities.append("user_engagement")
            if "api" in topics or "sdk" in topics:
                business_opportunities.append("platform_potential")

            return {
                "trend_score": round(trend_score, 2),
                "growth_rate": round(growth_rate, 2),
                "innovation_potential": round(innovation_potential, 2),
                "business_opportunity": ",".join(business_opportunities) if business_opportunities else None
            }

        except Exception as e:
            logger.warning(f"Error analyzing repository trends: {e}")
            return {
                "trend_score": 0.0,
                "growth_rate": 0.0,
                "innovation_potential": 0.5,
                "business_opportunity": None
            }

    def _analyze_issue_for_opportunities(self, issue) -> Dict[str, Any]:
        """Analyze issue for business opportunities"""
        try:
            title_lower = issue.title.lower() if issue.title else ""
            body_lower = issue.body.lower() if issue.body else ""
            combined_text = f"{title_lower} {body_lower}"

            # Pain point indicators
            pain_point_keywords = [
                "problem", "issue", "bug", "broken", "doesn't work", "frustrating",
                "difficult", "confusing", "slow", "crash", "error", "fail"
            ]

            # Feature request indicators
            feature_keywords = [
                "feature request", "would be nice", "add", "implement", "create",
                "support", "enhancement", "improvement", "extend", "expand"
            ]

            # Market demand indicators
            market_keywords = [
                "need", "want", "looking for", "wish", "require", "missing",
                "pay for", "subscribe", "premium", "commercial"
            ]

            pain_point_score = 0
            feature_request_score = 0
            market_signal = "none"

            # Count occurrences
            for keyword in pain_point_keywords:
                if keyword in combined_text:
                    pain_point_score += 1

            for keyword in feature_keywords:
                if keyword in combined_text:
                    feature_request_score += 1

            # Identify market signals
            for keyword in market_keywords:
                if keyword in combined_text:
                    market_signal = "market_demand"
                    break

            if issue.reactions and issue.reactions.totalCount > 10:
                market_signal = "high_engagement"

            # Generate business idea
            business_idea = None
            if feature_request_score > 0 or market_signal != "none":
                business_idea = f"Based on issue '{issue.title}': " \
                               f"Consider addressing {feature_request_score} feature requests " \
                               f"and {pain_point_score} pain points with {market_signal} signals"

            return {
                "pain_point_score": round(min(1.0, pain_point_score / 5.0), 2),
                "feature_request_score": round(min(1.0, feature_request_score / 5.0), 2),
                "market_signal": market_signal,
                "business_idea": business_idea
            }

        except Exception as e:
            logger.warning(f"Error analyzing issue for opportunities: {e}")
            return {
                "pain_point_score": 0.0,
                "feature_request_score": 0.0,
                "market_signal": "none",
                "business_idea": None
            }

    def _analyze_commit_for_features(self, commit) -> Dict[str, Any]:
        """Analyze commit for feature indicators"""
        try:
            message_lower = commit.commit.message.lower() if commit.commit.message else ""

            # Feature indicators
            feature_indicators = []
            if any(word in message_lower for word in ["add", "implement", "create", "build"]):
                feature_indicators.append("feature_added")
            if any(word in message_lower for word in ["fix", "patch", "resolve", "bug"]):
                feature_indicators.append("bug_fixed")
            if any(word in message_lower for word in ["improve", "enhance", "optimize", "refactor"]):
                feature_indicators.append("improvement")
            if any(word in message_lower for word in ["api", "endpoint", "rest", "graphql"]):
                feature_indicators.append("api_work")
            if any(word in message_lower for word in ["test", "spec", "unit", "integration"]):
                feature_indicators.append("testing")

            # Innovation signals
            innovation_keywords = ["ai", "ml", "machine learning", "blockchain", "crypto", "web3"]
            innovation_signals = []
            for keyword in innovation_keywords:
                if keyword in message_lower:
                    innovation_signals.append(keyword)

            # Development activity level
            activity_level = "maintenance"
            if commit.stats:
                total_changes = commit.stats.get('additions', 0) + commit.stats.get('deletions', 0)
                if total_changes > 500:
                    activity_level = "major_feature"
                elif total_changes > 100:
                    activity_level = "feature_work"
                elif total_changes > 50:
                    activity_level = "enhancement"

            return {
                "feature_indicators": ",".join(feature_indicators) if feature_indicators else None,
                "innovation_signals": ",".join(innovation_signals) if innovation_signals else None,
                "development_activity": activity_level
            }

        except Exception as e:
            logger.warning(f"Error analyzing commit for features: {e}")
            return {
                "feature_indicators": None,
                "innovation_signals": None,
                "development_activity": "maintenance"
            }

    def _analyze_contributor_expertise(self, contributor) -> Dict[str, Any]:
        """Analyze contributor's expertise and innovation potential"""
        try:
            # Calculate expertise score based on contributions
            expertise_score = min(1.0, 0.5)  # Base score

            # Boost score for high contribution count
            if hasattr(contributor, 'contributions'):
                contributions = contributor.contributions
                if contributions > 1000:
                    expertise_score += 0.3
                elif contributions > 100:
                    expertise_score += 0.2

            # Innovation index based on user details
            innovation_index = 0.5
            user = self.github.get_user(contributor.login)

            # Look for innovation indicators in bio and company
            bio_text = user.bio.lower() if user.bio else ""
            company_text = user.company.lower() if user.company else ""

            innovation_indicators = ["ai", "machine learning", "blockchain", "startup", "founder", "cto", "innovation"]
            for indicator in innovation_indicators:
                if indicator in bio_text or indicator in company_text:
                    innovation_index += 0.1

            innovation_index = min(1.0, innovation_index)

            # Technical skills based on public repositories
            technical_skills = []
            try:
                repos = list(user.get_repos(type='public'))[:10]  # Limit to 10 repos
                languages_used = set()
                for repo in repos:
                    if repo.language:
                        languages_used.add(repo.language)

                technical_skills = list(languages_used)
            except:
                pass

            return {
                "expertise_score": round(expertise_score, 2),
                "innovation_index": round(innovation_index, 2),
                "technical_skills": ",".join(technical_skills) if technical_skills else None
            }

        except Exception as e:
            logger.warning(f"Error analyzing contributor expertise: {e}")
            return {
                "expertise_score": 0.5,
                "innovation_index": 0.5,
                "technical_skills": None
            }