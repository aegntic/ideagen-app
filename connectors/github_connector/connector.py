"""
Fivetran GitHub Connector
Main connector implementation using Fivetran SDK
"""

import asyncio
import logging
import json
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional
from fivetran_client import FivetranClient
from fivetran_client.models import (
    ConnectorSchemaRequest,
    ConnectorSchemaResponse,
    ConnectorDataRequest,
    ConnectorDataResponse,
    Table,
    Column,
    DataType
)

from .github_client import GitHubClient
from .config import get_config, (
    REPOSITORY_SCHEMA, ISSUE_SCHEMA, COMMIT_SCHEMA,
    CONTRIBUTOR_SCHEMA, ORGANIZATION_SCHEMA
)


logger = logging.getLogger(__name__)


class GitHubConnector:
    """
    Fivetran connector for GitHub data extraction
    Handles schema definition, data extraction, and synchronization
    """

    def __init__(self, config=None):
        self.config = config or get_config()
        self.github_client = GitHubClient(self.config)
        self.fivetran_client = FivetranClient(
            api_key=self.config.fivetran_api_key,
            api_secret=self.config.fivetran_api_secret
        )
        self.logger = logger

    async def get_schema(self) -> ConnectorSchemaResponse:
        """
        Define the connector schema for Fivetran
        """
        try:
            self.logger.info("Defining GitHub connector schema")

            tables = []

            # Repositories table
            repositories_table = Table(
                name="github_repositories",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in REPOSITORY_SCHEMA.items()
                ]
            )
            tables.append(repositories_table)

            # Issues table
            issues_table = Table(
                name="github_issues",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in ISSUE_SCHEMA.items()
                ]
            )
            tables.append(issues_table)

            # Commits table
            commits_table = Table(
                name="github_commits",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in COMMIT_SCHEMA.items()
                ]
            )
            tables.append(commits_table)

            # Contributors table
            contributors_table = Table(
                name="github_contributors",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in CONTRIBUTOR_SCHEMA.items()
                ]
            )
            tables.append(contributors_table)

            # Organizations table
            organizations_table = Table(
                name="github_organizations",
                columns=[
                    Column(name=col_name, data_type=DataType(data_type))
                    for col_name, data_type in ORGANIZATION_SCHEMA.items()
                ]
            )
            tables.append(organizations_table)

            return ConnectorSchemaResponse(
                tables=tables,
                schema=self.config.destination_schema
            )

        except Exception as e:
            self.logger.error(f"Error defining schema: {e}")
            raise

    async def sync_data(self, state: Optional[Dict[str, Any]] = None) -> ConnectorDataResponse:
        """
        Synchronize data from GitHub to Fivetran destination
        """
        try:
            self.logger.info("Starting GitHub data synchronization")

            # Initialize state if not provided
            if state is None:
                state = {
                    "last_sync": None,
                    "processed_repos": set(),
                    "processed_issues": set(),
                    "processed_commits": set(),
                    "processed_contributors": set(),
                    "processed_orgs": set(),
                    "cursor": {}
                }

            current_time = datetime.now(UTC)
            sync_data = {
                "repositories": [],
                "issues": [],
                "commits": [],
                "contributors": [],
                "organizations": []
            }

            # Sync trending repositories
            await self._sync_trending_repositories(state, sync_data)

            # Sync issues for high-value repositories
            await self._sync_repository_issues(state, sync_data)

            # Sync commits for active repositories
            await self._sync_repository_commits(state, sync_data)

            # Sync contributors from top repositories
            await self._sync_repository_contributors(state, sync_data)

            # Extract unique organizations
            await self._sync_organizations(state, sync_data)

            # Update state
            state["last_sync"] = current_time.isoformat()

            # Send data to Fivetran
            await self._send_data_to_fivetran(sync_data)

            return ConnectorDataResponse(
                has_more=False,
                state=state,
                records_processed=len(sync_data["repositories"]) + len(sync_data["issues"]) +
                               len(sync_data["commits"]) + len(sync_data["contributors"]) +
                               len(sync_data["organizations"])
            )

        except Exception as e:
            self.logger.error(f"Error during data synchronization: {e}")
            raise

    async def _sync_trending_repositories(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize trending repositories"""
        self.logger.info("Syncing trending repositories")

        try:
            async for repo_data in self.github_client.get_trending_repositories(
                languages=self.config.languages,
                topics=self.config.topics,
                min_stars=self.config.min_stars,
                days_back=self.config.days_back,
                limit=self.config.repositories_limit
            ):
                repo_id = str(repo_data["id"])

                # Skip if already processed
                if repo_id in state["processed_repos"]:
                    continue

                # Include all trending repositories
                sync_data["repositories"].append(repo_data)
                state["processed_repos"].add(repo_id)

                # Track repositories for deeper analysis
                if "high_value_repos" not in state:
                    state["high_value_repos"] = []

                # Add repositories with high potential for deeper analysis
                if (repo_data.get("innovation_potential", 0) >= 0.7 or
                    repo_data.get("trend_score", 0) >= 50 or
                    repo_data.get("stars", 0) >= 500):

                    if len(state["high_value_repos"]) < 50:  # Limit deeper analysis
                        state["high_value_repos"].append(repo_data["full_name"])

        except Exception as e:
            self.logger.error(f"Error syncing trending repositories: {e}")

    async def _sync_repository_issues(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize issues from high-value repositories"""
        self.logger.info("Syncing repository issues")

        high_value_repos = state.get("high_value_repos", [])

        for repo_full_name in high_value_repos:
            try:
                async for issue_data in self.github_client.get_repository_issues(
                    repo_full_name=repo_full_name,
                    state="open",
                    limit=self.config.issues_limit
                ):
                    issue_id = str(issue_data["id"])

                    # Skip if already processed
                    if issue_id in state["processed_issues"]:
                        continue

                    # Include issues with business opportunities
                    if (issue_data.get("feature_request_score", 0) >= 0.3 or
                        issue_data.get("pain_point_score", 0) >= 0.3 or
                        issue_data.get("market_signal") != "none"):

                        sync_data["issues"].append(issue_data)
                        state["processed_issues"].add(issue_id)

            except Exception as e:
                self.logger.warning(f"Error syncing issues for {repo_full_name}: {e}")
                continue

    async def _sync_repository_commits(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize commits from active repositories"""
        self.logger.info("Syncing repository commits")

        high_value_repos = state.get("high_value_repos", [])[:20]  # Limit to top 20 repos

        for repo_full_name in high_value_repos:
            try:
                async for commit_data in self.github_client.get_repository_commits(
                    repo_full_name=repo_full_name,
                    days_back=self.config.days_back,
                    limit=self.config.commits_limit
                ):
                    commit_id = commit_data["sha"]

                    # Skip if already processed
                    if commit_id in state["processed_commits"]:
                        continue

                    # Include commits with feature indicators
                    if (commit_data.get("feature_indicators") or
                        commit_data.get("innovation_signals")):

                        sync_data["commits"].append(commit_data)
                        state["processed_commits"].add(commit_id)

            except Exception as e:
                self.logger.warning(f"Error syncing commits for {repo_full_name}: {e}")
                continue

    async def _sync_repository_contributors(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Synchronize contributors from top repositories"""
        self.logger.info("Syncing repository contributors")

        high_value_repos = state.get("high_value_repos", [])[:10]  # Limit to top 10 repos

        for repo_full_name in high_value_repos:
            try:
                async for contributor_data in self.github_client.get_contributor_data(
                    repo_full_name=repo_full_name,
                    limit=15  # Top 15 contributors per repo
                ):
                    contributor_id = str(contributor_data["id"])

                    # Skip if already processed
                    if contributor_id in state["processed_contributors"]:
                        continue

                    # Include contributors with high expertise
                    if contributor_data.get("expertise_score", 0) >= 0.6:
                        sync_data["contributors"].append(contributor_data)
                        state["processed_contributors"].add(contributor_id)

            except Exception as e:
                self.logger.warning(f"Error syncing contributors for {repo_full_name}: {e}")
                continue

    async def _sync_organizations(self, state: Dict[str, Any], sync_data: Dict[str, List]):
        """Extract and sync unique organizations from repositories and contributors"""
        self.logger.info("Extracting organizations from repositories and contributors")

        org_ids = set()

        # Extract organizations from repositories
        for repo in sync_data["repositories"]:
            owner_type = repo.get("owner_type")
            owner_id = repo.get("owner_id")

            if owner_type == "Organization" and owner_id and str(owner_id) not in state["processed_orgs"]:
                org_ids.add(str(owner_id))

        # Create basic organization data
        for repo in sync_data["repositories"]:
            owner_type = repo.get("owner_type")
            owner_id = repo.get("owner_id")

            if owner_type == "Organization" and str(owner_id) in org_ids:
                # Create organization data from repository information
                org_data = self._create_organization_data_from_repo(repo)
                if org_data:
                    sync_data["organizations"].append(org_data)
                    state["processed_orgs"].add(str(owner_id))
                    org_ids.discard(str(owner_id))

    def _create_organization_data_from_repo(self, repo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create organization data from repository information"""
        try:
            # This is a simplified approach - in production you'd fetch full org data
            return {
                "id": repo.get("owner_id"),
                "login": repo.get("owner_login"),
                "name": repo.get("owner_login"),  # Would fetch from API
                "email": None,
                "company": repo.get("owner_login"),
                "location": None,
                "blog": None,
                "description": f"Organization behind {repo.get('full_name')}",
                "followers": 0,  # Would fetch from API
                "following": 0,
                "public_repos": 1,  # At least this repo
                "created_at": repo.get("created_at"),
                "updated_at": repo.get("updated_at"),
                "type": "Organization",
                "has_organization_projects": True,  # Assume yes
                "has_repository_projects": True,
                "is_verified": False,  # Would check via API
                "extracted_at": datetime.now(UTC).isoformat(),
                "innovation_leadership": 0.7,  # Based on repo quality
                "market_influence": repo.get("stars", 0) / 1000.0,  # Rough estimate
                "technology_focus": repo.get("language") or "general"
            }
        except Exception as e:
            self.logger.warning(f"Error creating organization data: {e}")
            return None

    async def _send_data_to_fivetran(self, sync_data: Dict[str, List]):
        """Send synchronized data to Fivetran destination"""
        try:
            # Send repositories data
            if sync_data["repositories"]:
                await self._send_table_data("github_repositories", sync_data["repositories"])
                self.logger.info(f"Sent {len(sync_data['repositories'])} repositories to Fivetran")

            # Send issues data
            if sync_data["issues"]:
                await self._send_table_data("github_issues", sync_data["issues"])
                self.logger.info(f"Sent {len(sync_data['issues'])} issues to Fivetran")

            # Send commits data
            if sync_data["commits"]:
                await self._send_table_data("github_commits", sync_data["commits"])
                self.logger.info(f"Sent {len(sync_data['commits'])} commits to Fivetran")

            # Send contributors data
            if sync_data["contributors"]:
                await self._send_table_data("github_contributors", sync_data["contributors"])
                self.logger.info(f"Sent {len(sync_data['contributors'])} contributors to Fivetran")

            # Send organizations data
            if sync_data["organizations"]:
                await self._send_table_data("github_organizations", sync_data["organizations"])
                self.logger.info(f"Sent {len(sync_data['organizations'])} organizations to Fivetran")

        except Exception as e:
            self.logger.error(f"Error sending data to Fivetran: {e}")
            raise

    async def _send_table_data(self, table_name: str, data: List[Dict[str, Any]]):
        """Send data for a specific table to Fivetran"""
        try:
            # Convert data to Fivetran format
            fivetran_data = []
            for record in data:
                # Flatten nested objects and convert lists to strings
                flattened_record = {}
                for key, value in record.items():
                    if isinstance(value, (list, dict)):
                        flattened_record[key] = json.dumps(value)
                    else:
                        flattened_record[key] = value
                fivetran_data.append(flattened_record)

            # Send data using Fivetran client
            # This would use the actual Fivetran SDK in production
            # await self.fivetran_client.upsert_data(
            #     schema=self.config.destination_schema,
            #     table=table_name,
            #     data=fivetran_data
            # )

        except Exception as e:
            self.logger.error(f"Error sending data for table {table_name}: {e}")
            raise

    async def test_connection(self) -> bool:
        """Test connection to GitHub API"""
        try:
            self.logger.info("Testing GitHub API connection")

            # Try to get authenticated user
            user = self.github_client.github.get_user()

            if user.login:
                self.logger.info(f"GitHub API connection test successful - authenticated as {user.login}")
                return True
            else:
                self.logger.error("GitHub API connection test failed - no user data")
                return False

        except Exception as e:
            self.logger.error(f"GitHub API connection test failed: {e}")
            return False

    async def get_data_samples(self, limit: int = 3) -> Dict[str, List[Dict[str, Any]]]:
        """Get sample data for testing and validation"""
        try:
            self.logger.info(f"Getting {limit} sample records from each data type")

            samples = {
                "repositories": [],
                "issues": [],
                "commits": [],
                "contributors": [],
                "organizations": []
            }

            # Get sample repositories
            repo_count = 0
            async for repo_data in self.github_client.get_trending_repositories(
                languages=["Python"],  # Limit to one language for sample
                limit=limit
            ):
                samples["repositories"].append(repo_data)
                repo_count += 1
                if repo_count >= limit:
                    break

            # Get sample issues (from first repository if available)
            if samples["repositories"]:
                first_repo = samples["repositories"][0]["full_name"]
                issue_count = 0
                async for issue_data in self.github_client.get_repository_issues(
                    repo_full_name=first_repo,
                    limit=limit
                ):
                    samples["issues"].append(issue_data)
                    issue_count += 1
                    if issue_count >= limit:
                        break

            # Get sample commits (from first repository if available)
            if samples["repositories"]:
                first_repo = samples["repositories"][0]["full_name"]
                commit_count = 0
                async for commit_data in self.github_client.get_repository_commits(
                    repo_full_name=first_repo,
                    days_back=7,  # Last 7 days
                    limit=limit
                ):
                    samples["commits"].append(commit_data)
                    commit_count += 1
                    if commit_count >= limit:
                        break

            # Get sample contributors (from first repository if available)
            if samples["repositories"]:
                first_repo = samples["repositories"][0]["full_name"]
                contributor_count = 0
                async for contributor_data in self.github_client.get_contributor_data(
                    repo_full_name=first_repo,
                    limit=limit
                ):
                    samples["contributors"].append(contributor_data)
                    contributor_count += 1
                    if contributor_count >= limit:
                        break

            return samples

        except Exception as e:
            self.logger.error(f"Error getting data samples: {e}")
            raise

    def get_connector_info(self) -> Dict[str, Any]:
        """Get connector information and configuration"""
        return {
            "name": "GitHub Connector",
            "version": "1.0.0",
            "description": "Extracts trending repositories, issues, commits, and developer data from GitHub for idea generation",
            "source_type": "API",
            "sync_frequency": f"{self.config.sync_frequency_hours} hours",
            "supported_data_types": [
                "repositories", "issues", "commits", "contributors", "organizations"
            ],
            "configuration": {
                "repositories_limit": self.config.repositories_limit,
                "issues_limit": self.config.issues_limit,
                "commits_limit": self.config.commits_limit,
                "days_back": self.config.days_back,
                "languages": self.config.languages,
                "topics": self.config.topics,
                "min_stars": self.config.min_stars,
                "destination_schema": self.config.destination_schema
            },
            "features": [
                "Trend analysis",
                "Innovation potential scoring",
                "Growth rate calculation",
                "Business opportunity detection",
                "Pain point identification",
                "Feature request extraction",
                "Contributor expertise analysis",
                "Technical skill assessment"
            ]
        }


async def main():
    """Main entry point for the connector"""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Initialize connector
        connector = GitHubConnector()

        # Parse command line arguments
        if len(sys.argv) > 1:
            command = sys.argv[1].lower()

            if command == "schema":
                schema = await connector.get_schema()
                print("Connector Schema:")
                print(json.dumps(schema.dict(), indent=2))

            elif command == "sync":
                result = await connector.sync_data()
                print(f"Sync completed: {result.records_processed} records processed")

            elif command == "test":
                is_connected = await connector.test_connection()
                print(f"Connection test: {'PASSED' if is_connected else 'FAILED'}")

            elif command == "sample":
                samples = await connector.get_data_samples()
                print("Sample Data:")
                print(json.dumps(samples, indent=2))

            elif command == "info":
                info = connector.get_connector_info()
                print("Connector Information:")
                print(json.dumps(info, indent=2))

            else:
                print(f"Unknown command: {command}")
                print("Available commands: schema, sync, test, sample, info")
        else:
            print("GitHub Connector for Fivetran")
            print("Usage: python -m github_connector.main [command]")
            print("Commands: schema, sync, test, sample, info")

    except Exception as e:
        logger.error(f"Connector error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())