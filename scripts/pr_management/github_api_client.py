#!/usr/bin/env python3
"""
GitHub API Client for PR Management Operations
Provides robust GitHub API integration with error handling, rate limiting, and caching.
"""

import os
import time
import subprocess
from typing import Dict, List, Optional
from datetime import datetime
import requests
from functools import lru_cache
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PRInfo:
    """Pull Request information container"""

    number: int
    title: str
    state: str
    author: str
    created_at: datetime
    updated_at: datetime
    head_branch: str
    base_branch: str
    mergeable: Optional[bool]
    mergeable_state: Optional[str]
    additions: int
    deletions: int
    changed_files: int
    labels: List[str]
    reviewers: List[str]
    status_checks: Dict[str, str]
    is_dependabot: bool
    is_security: bool
    conflicts: bool
    body: str


class GitHubAPIClient:
    """Robust GitHub API client for PR management operations"""

    def __init__(
        self, owner: str = None, repo: str = None, token: str = None, dry_run: bool = False
    ) -> None:
        """Initialize GitHub API client"""
        self.owner = owner or os.getenv("GITHUB_OWNER", "OmarA1-Bakri")
        self.repo = repo or os.getenv("GITHUB_REPO", "ruleIQ")
        self.token = token or self._get_github_token()
        self.dry_run = dry_run
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"token {self.token}" if self.token else "",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._cache = {}
        self._rate_limit_reset = None

    def _get_github_token(self) -> Optional[str]:
        """Get GitHub token from environment or gh CLI"""
        # Try environment variable first
        token = os.getenv("GITHUB_TOKEN")
        if token:
            return token

        # Try gh CLI
        try:
            result = subprocess.run(
                ["gh", "auth", "token"], capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("No GitHub token found. API requests may be rate limited.")
            return None

    def _is_success(self, response: requests.Response) -> bool:
        """Check if response indicates success (any 2xx status)"""
        return 200 <= response.status_code < 300

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """Handle GitHub API rate limiting"""
        if response.status_code == 403 and "rate limit" in response.text.lower():
            reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait_time = max(reset_time - time.time(), 1)
            logger.warning(f"Rate limit hit. Waiting {wait_time:.0f} seconds...")
            time.sleep(wait_time)

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Make API request with error handling and retries.

        Returns:
            - JSON response for 2xx with body
            - {'ok': True, 'status': <code>} for 2xx without body (204, etc.)
            - None for failures
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}{endpoint}"

        for attempt in range(3):  # Retry up to 3 times
            try:
                response = self.session.request(method, url, **kwargs)

                if self._is_success(response):
                    # Handle 204 No Content or other 2xx with no body
                    if response.status_code == 204 or not response.content:
                        return {"ok": True, "status": response.status_code}

                    # Try to parse JSON for other 2xx responses
                    try:
                        return response.json()
                    except ValueError:
                        # If JSON parsing fails but it's still 2xx, return success indicator
                        return {"ok": True, "status": response.status_code}

                elif response.status_code == 403:
                    self._handle_rate_limit(response)
                    continue
                else:
                    logger.error(f"API request failed: {response.status_code} - {response.text}")
                    return None

            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {e}")
                if attempt < 2:
                    time.sleep(2**attempt)  # Exponential backoff
                    continue
                return None

        return None

    @lru_cache(maxsize=128)
    def get_pr(self, pr_number: int) -> Optional[PRInfo]:
        """Get detailed information for a specific PR"""
        pr_data = self._make_request("GET", f"/pulls/{pr_number}")
        if not pr_data:
            return None

        # Get additional status check information
        status_checks = self.get_pr_status_checks(pr_number)

        return PRInfo(
            number=pr_data["number"],
            title=pr_data["title"],
            state=pr_data["state"],
            author=pr_data["user"]["login"],
            created_at=datetime.fromisoformat(pr_data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(pr_data["updated_at"].replace("Z", "+00:00")),
            head_branch=pr_data["head"]["ref"],
            base_branch=pr_data["base"]["ref"],
            mergeable=pr_data.get("mergeable"),
            mergeable_state=pr_data.get("mergeable_state"),
            additions=pr_data.get("additions", 0),
            deletions=pr_data.get("deletions", 0),
            changed_files=pr_data.get("changed_files", 0),
            labels=[label["name"] for label in pr_data.get("labels", [])],
            reviewers=[reviewer["login"] for reviewer in pr_data.get("requested_reviewers", [])],
            status_checks=status_checks,
            is_dependabot="dependabot" in pr_data["user"]["login"].lower(),
            is_security=any(
                "security" in label["name"].lower() for label in pr_data.get("labels", [])
            ),
            conflicts=pr_data.get("mergeable_state") == "conflicting",
            body=pr_data.get("body", ""),
        )

    def get_all_open_prs(self) -> List[PRInfo]:
        """Get all open pull requests"""
        prs = []
        page = 1

        while True:
            response = self._make_request(
                "GET", "/pulls", params={"state": "open", "per_page": 100, "page": page}
            )

            if not response:
                break

            for pr_data in response:
                pr_info = self.get_pr(pr_data["number"])
                if pr_info:
                    prs.append(pr_info)

            if len(response) < 100:
                break

            page += 1

        return prs

    def get_pr_status_checks(self, pr_number: int) -> Dict[str, str]:
        """Get CI/CD status checks for a PR with pagination support"""
        pr_data = self._make_request("GET", f"/pulls/{pr_number}")
        if not pr_data:
            return {}

        sha = pr_data["head"]["sha"]
        checks = {}

        # Get classic commit statuses
        status_data = self._make_request("GET", f"/commits/{sha}/status")
        if status_data:
            for status in status_data.get("statuses", []):
                checks[status["context"]] = status["state"]

        # Get check runs with pagination
        page = 1
        per_page = 100
        while True:
            check_runs = self._make_request(
                "GET", f"/commits/{sha}/check-runs", params={"page": page, "per_page": per_page}
            )

            if not check_runs or "check_runs" not in check_runs:
                break

            for run in check_runs["check_runs"]:
                # Normalize status: use conclusion if present, otherwise map status
                if run.get("conclusion"):
                    status = run["conclusion"]
                elif run["status"] == "completed":
                    status = "success"
                elif run["status"] in ["queued", "in_progress"]:
                    status = "pending"
                else:
                    status = run["status"]

                # Avoid overwriting existing checks with same name
                check_name = run["name"]
                if check_name not in checks:
                    checks[check_name] = status

            # Check if we have more pages
            if len(check_runs["check_runs"]) < per_page:
                break
            page += 1

        return checks

    def merge_pr(
        self,
        pr_number: int,
        merge_method: str = "merge",
        commit_title: str = None,
        commit_message: str = None,
    ) -> bool:
        """Merge a pull request"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would merge PR #{pr_number} using {merge_method}")
            return True

        payload = {"merge_method": merge_method}
        if commit_title:
            payload["commit_title"] = commit_title
        if commit_message:
            payload["commit_message"] = commit_message

        response = self._make_request("PUT", f"/pulls/{pr_number}/merge", json=payload)

        if response:
            logger.info(f"Successfully merged PR #{pr_number}")
            return True
        else:
            logger.error(f"Failed to merge PR #{pr_number}")
            return False

    def close_pr(self, pr_number: int) -> bool:
        """Close a pull request without merging"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would close PR #{pr_number}")
            return True

        response = self._make_request("PATCH", f"/pulls/{pr_number}", json={"state": "closed"})

        if response:
            logger.info(f"Successfully closed PR #{pr_number}")
            return True
        else:
            logger.error(f"Failed to close PR #{pr_number}")
            return False

    def add_pr_comment(self, pr_number: int, comment: str) -> bool:
        """Add a comment to a pull request"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would add comment to PR #{pr_number}: {comment[:100]}...")
            return True

        response = self._make_request(
            "POST", f"/issues/{pr_number}/comments", json={"body": comment}
        )

        if response:
            logger.info(f"Successfully added comment to PR #{pr_number}")
            return True
        else:
            logger.error(f"Failed to add comment to PR #{pr_number}")
            return False

    def approve_pr(self, pr_number: int, comment: str = "LGTM") -> bool:
        """Approve a pull request"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would approve PR #{pr_number}")
            return True

        response = self._make_request(
            "POST", f"/pulls/{pr_number}/reviews", json={"event": "APPROVE", "body": comment}
        )

        if response:
            logger.info(f"Successfully approved PR #{pr_number}")
            return True
        else:
            logger.error(f"Failed to approve PR #{pr_number}")
            return False

    def get_pr_files(self, pr_number: int) -> List[Dict]:
        """Get list of files changed in a PR"""
        files = []
        page = 1

        while True:
            response = self._make_request(
                "GET", f"/pulls/{pr_number}/files", params={"per_page": 100, "page": page}
            )

            if not response:
                break

            files.extend(response)

            if len(response) < 100:
                break

            page += 1

        return files

    def get_pr_reviews(self, pr_number: int) -> List[Dict]:
        """Get reviews for a pull request"""
        response = self._make_request("GET", f"/pulls/{pr_number}/reviews")
        return response or []

    def check_pr_conflicts(self, pr_number: int) -> bool:
        """Check if a PR has merge conflicts"""
        pr_info = self.get_pr(pr_number)
        return pr_info.conflicts if pr_info else False

    def update_branch(self, pr_number: int) -> bool:
        """Update PR branch with base branch"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update branch for PR #{pr_number}")
            return True

        response = self._make_request("PUT", f"/pulls/{pr_number}/update-branch")

        # Accept 202 Accepted or any successful response
        if response and (response.get("ok") or response.get("status") == 202 or "sha" in response):
            logger.info(f"Successfully updated branch for PR #{pr_number}")
            return True
        else:
            logger.error(f"Failed to update branch for PR #{pr_number}")
            return False

    def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete branch {branch_name}")
            return True

        response = self._make_request("DELETE", f"/git/refs/heads/{branch_name}")

        # Accept 204 No Content or any successful response
        if response and (response.get("ok") or response.get("status") == 204):
            logger.info(f"Successfully deleted branch {branch_name}")
            return True
        else:
            logger.error(f"Failed to delete branch {branch_name}")
            return False

    def get_workflow_runs(self, branch: str = None) -> List[Dict]:
        """Get workflow runs for a branch"""
        params = {"per_page": 30}
        if branch:
            params["branch"] = branch

        response = self._make_request("GET", "/actions/runs", params=params)
        return response.get("workflow_runs", []) if response else []

    def rerun_workflow(self, run_id: int) -> bool:
        """Rerun a workflow"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would rerun workflow {run_id}")
            return True

        response = self._make_request("POST", f"/actions/runs/{run_id}/rerun")

        # Accept 201 Created, 202 Accepted, or any successful response
        if response and (response.get("ok") or response.get("status") in [201, 202]):
            logger.info(f"Successfully reran workflow {run_id}")
            return True
        else:
            logger.error(f"Failed to rerun workflow {run_id}")
            return False

    def get_rate_limit_status(self) -> Dict:
        """Get current rate limit status"""
        response = requests.get(f"{self.base_url}/rate_limit", headers=self.headers)
        if response.status_code == 200:
            return response.json()
        return {}


if __name__ == "__main__":
    # Example usage
    client = GitHubAPIClient(dry_run=True)

    # Get all open PRs
    prs = client.get_all_open_prs()
    print(f"Found {len(prs)} open PRs")

    for pr in prs[:5]:  # Show first 5
        print(f"\nPR #{pr.number}: {pr.title}")
        print(f"  Author: {pr.author}")
        print(f"  Status: {pr.state}")
        print(f"  Dependabot: {pr.is_dependabot}")
        print(f"  Security: {pr.is_security}")
        print(f"  Changes: +{pr.additions}/-{pr.deletions} in {pr.changed_files} files")
