#!/usr/bin/env python3
"""
Execute Organization-Level Deployment for ruleIQ
Manages the complete deployment process with monitoring and validation
"""

import json
import os
import subprocess
import sys
import time
import requests
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
import argparse


class Colors:
    """Terminal colors for output formatting"""

    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    MAGENTA = "\033[0;35m"
    CYAN = "\033[0;36m"
    NC = "\033[0m"  # No Color
    BOLD = "\033[1m"


class DeploymentExecutor:
    def __init__(
        self,
        environment: str = "production",
        non_interactive: bool = False,
        strict_validation: bool = False,
        require_org_remote: bool = False,
    ) -> None:
        self.environment = environment
        self.non_interactive = non_interactive
        self.strict_validation = strict_validation
        self.require_org_remote = require_org_remote
        self.org_name = "RuleIQ-Vercel-Deploy"
        self.repo_name = "ruleIQ"
        self.start_time = datetime.now()
        self.deployment_url = None
        self.vercel_cli_available = False
        self.deployment_method = None
        self.doppler_available = False  # Track Doppler availability
        self.report = {
            "timestamp": self.start_time.isoformat(),
            "environment": environment,
            "organization": self.org_name,
            "repository": self.repo_name,
            "status": "started",
            "steps": [],
            "metrics": {},
            "errors": [],
            "warnings": [],
            "doppler_enabled": False,  # Track if Doppler was used
        }

    def print_header(self, message: str):
        """Print formatted section header"""
        print(f"\n{Colors.BLUE}{'=' * 60}{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}{message}{Colors.NC}")
        print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}\n")

    def print_success(self, message: str):
        """Print success message"""
        print(f"{Colors.GREEN}✅ {message}{Colors.NC}")
        self.report["steps"].append({"status": "success", "message": message})

    def print_warning(self, message: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.NC}")
        self.report["warnings"].append(message)

    def print_error(self, message: str):
        """Print error message"""
        print(f"{Colors.RED}❌ {message}{Colors.NC}")
        self.report["errors"].append(message)

    def print_info(self, message: str):
        """Print info message"""
        print(f"{Colors.BLUE}ℹ️  {message}{Colors.NC}")

    def print_progress(self, message: str):
        """Print progress indicator"""
        print(f"{Colors.YELLOW}⏳ {message}...{Colors.NC}", end="", flush=True)

    def run_command(self, command: str, check: bool = True) -> Tuple[bool, str]:
        """Run shell command and return result"""
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
        output = (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")
        if check and result.returncode != 0:
            return False, output
        return result.returncode == 0, output

    def pre_deployment_validation(self) -> bool:
        """Run pre-deployment validation checks"""
        self.print_header("PRE-DEPLOYMENT VALIDATION")

        checks = []

        # Check git status
        self.print_progress("Checking git status")
        success, output = self.run_command("git status --porcelain")
        if success:
            if output.strip():
                print(f" {Colors.YELLOW}[UNCOMMITTED CHANGES]{Colors.NC}")
                self.print_warning("You have uncommitted changes")
                self.print_info("Consider committing or stashing changes before deployment")
            else:
                print(f" {Colors.GREEN}[CLEAN]{Colors.NC}")
                self.print_success("Working directory clean")
            checks.append(True)
        else:
            print(f" {Colors.RED}[FAILED]{Colors.NC}")
            self.print_error("Failed to check git status")
            checks.append(False)

        # Check current branch
        self.print_progress("Checking current branch")
        success, branch = self.run_command("git branch --show-current")
        if success:
            branch = branch.strip()
            print(f" {Colors.CYAN}[{branch}]{Colors.NC}")
            if branch == "main":
                self.print_success("On main branch")
            else:
                self.print_warning(f"On branch '{branch}' - deployment typically uses 'main'")
            checks.append(True)
        else:
            print(f" {Colors.RED}[FAILED]{Colors.NC}")
            checks.append(False)

        # Check remote repository
        self.print_progress("Verifying remote repository")
        success, remote = self.run_command("git remote get-url origin")
        if success and f"{self.org_name}/{self.repo_name}" in remote:
            print(f" {Colors.GREEN}[ORGANIZATION]{Colors.NC}")
            self.print_success("Connected to organization repository")
            checks.append(True)
        elif self.require_org_remote:
            print(f" {Colors.RED}[INCORRECT]{Colors.NC}")
            self.print_error("Not connected to organization repository")
            self.print_info(f"Expected: https://github.com/{self.org_name}/{self.repo_name}.git")
            self.print_info(
                "Run scripts/deploy/update-git-remote.sh to update your remote to the organization repository"
            )
            checks.append(False)
        else:
            print(f" {Colors.YELLOW}[WARNING]{Colors.NC}")
            self.print_warning("Not connected to organization repository")
            self.print_info(f"Expected: https://github.com/{self.org_name}/{self.repo_name}.git")
            self.print_info(
                "Run scripts/deploy/update-git-remote.sh to update your remote to the organization repository"
            )
            # Still append True to not block deployment for non-standard remotes
            checks.append(True)

        # Check Vercel CLI
        self.print_progress("Checking Vercel CLI")
        success, _ = self.run_command("vercel --version", check=False)
        if success:
            print(f" {Colors.GREEN}[INSTALLED]{Colors.NC}")
            self.vercel_cli_available = True
            checks.append(True)
        else:
            print(f" {Colors.YELLOW}[NOT INSTALLED]{Colors.NC}")
            self.print_warning("Vercel CLI not installed - GitHub Actions will handle deployment")
            self.vercel_cli_available = False
            checks.append(True)  # Not critical

        # Check Doppler integration
        self.print_progress("Checking Doppler integration")
        doppler_token = os.environ.get("DOPPLER_TOKEN")
        if doppler_token:
            print(f" {Colors.GREEN}[CONFIGURED]{Colors.NC}")
            self.print_success("Doppler is configured for secrets management")
            self.doppler_available = True
            self.report["doppler_enabled"] = True
            checks.append(True)
        else:
            print(f" {Colors.YELLOW}[NOT CONFIGURED]{Colors.NC}")
            self.print_info("Doppler not configured - will use standard secrets")
            self.print_info("Run scripts/deploy/configure-doppler-secrets.sh to enable Doppler")
            self.doppler_available = False
            checks.append(True)  # Not critical

        return all(checks)

    def trigger_github_actions_deployment(self) -> bool:
        """Trigger deployment via GitHub Actions"""
        self.print_header("TRIGGERING GITHUB ACTIONS DEPLOYMENT")

        # Inform about which workflow will be used
        if self.doppler_available:
            self.print_info("Using Doppler-integrated workflow (deploy-vercel-doppler.yml)")
            self.print_success("Secrets will be managed through Doppler")
        else:
            self.print_info("Using standard workflow (deploy-vercel.yml)")
            self.print_info("Consider configuring Doppler for enterprise-grade secrets management")

        # Push to remote
        self.print_progress("Pushing to organization repository")
        success, output = self.run_command("git push origin main", check=False)

        if success:
            print(f" {Colors.GREEN}[SUCCESS]{Colors.NC}")
            self.print_success("Code pushed to organization repository")
            self.print_info("GitHub Actions workflow triggered")

            # Provide monitoring links
            actions_url = f"https://github.com/{self.org_name}/{self.repo_name}/actions"
            print(f"\n{Colors.MAGENTA}📊 Monitor deployment at:{Colors.NC}")
            print(f"   {Colors.BLUE}{actions_url}{Colors.NC}")

            self.report["deployment_method"] = "github_actions"
            self.report["monitoring_url"] = actions_url
            self.report["workflow_used"] = (
                "deploy-vercel-doppler.yml" if self.doppler_available else "deploy-vercel.yml"
            )
            self.deployment_method = "github"

            return True
        else:
            print(f" {Colors.RED}[FAILED]{Colors.NC}")
            # Improved up-to-date heuristic (case-insensitive and more robust)
            if "up-to-date" in output.lower() or "everything up-to-date" in output.lower():
                self.print_info("Repository already up-to-date")
                self.print_info("Deployment may have been triggered previously")
                return True
            else:
                self.print_error(f"Failed to push: {output}")
                return False

    def trigger_vercel_cli_deployment(self) -> bool:
        """Deploy directly using Vercel CLI"""
        self.print_header("VERCEL CLI DEPLOYMENT")
        self.deployment_method = "vercel"

        # Get environment variables for proper scoping
        vercel_org_id = os.environ.get("VERCEL_ORG_ID")
        vercel_project_id = os.environ.get("VERCEL_PROJECT_ID")
        vercel_token = os.environ.get("VERCEL_TOKEN")

        # Check for .vercel/project.json to ensure correct project/org
        vercel_config_path = Path(".vercel/project.json")
        if vercel_config_path.exists():
            try:
                with open(vercel_config_path, "r") as f:
                    vercel_config = json.load(f)
                    configured_org = vercel_config.get("orgId", "")
                    configured_project = vercel_config.get("projectId", "")

                    # Use config values if env vars not set
                    if not vercel_org_id:
                        vercel_org_id = configured_org
                    if not vercel_project_id:
                        vercel_project_id = configured_project

                    self.print_info(
                        f"Using Vercel project: {configured_project} (org: {configured_org})"
                    )
            except Exception as e:
                self.print_warning(f"Could not read Vercel config: {str(e)}")

        # Check if project is linked
        self.print_progress("Checking Vercel project link")

        # Build command with token if available
        project_ls_cmd = "vercel project ls"
        if vercel_token:
            project_ls_cmd = f"vercel project ls --token={vercel_token}"
        if vercel_org_id:
            project_ls_cmd += f" --scope {vercel_org_id}"

        success, output = self.run_command(project_ls_cmd, check=False)
        if not success:
            print(f" {Colors.YELLOW}[NOT LINKED]{Colors.NC}")
            self.print_info("Linking project to organization...")

            if vercel_org_id and vercel_project_id:
                # Use environment variables to ensure correct linking
                link_cmd = f"VERCEL_ORG_ID={vercel_org_id} VERCEL_PROJECT_ID={vercel_project_id} vercel link --yes"
                if vercel_token:
                    link_cmd += f" --token={vercel_token}"
            else:
                link_cmd = "vercel link"

            success, _ = self.run_command(link_cmd, check=False)
            if not success:
                self.print_error("Failed to link Vercel project")
                return False

        # Deploy with JSON output for structured parsing
        environment_flag = "--prod" if self.environment == "production" else ""
        self.print_progress(f"Deploying to {self.environment}")

        # First, do the deployment with proper scoping
        deploy_cmd = f"vercel {environment_flag}"
        if vercel_token:
            deploy_cmd += f" --token={vercel_token}"
        if vercel_org_id:
            deploy_cmd += f" --scope {vercel_org_id}"

        success, output = self.run_command(deploy_cmd, check=False)

        if success:
            print(f" {Colors.GREEN}[SUCCESS]{Colors.NC}")

            # Try to extract deployment URL from output first
            if "https://" in output:
                for line in output.split("\n"):
                    if "https://" in line and "vercel.app" in line:
                        self.deployment_url = line.strip()
                        break

            # If not found, use vercel inspect to get deployment info
            if not self.deployment_url:
                # Build properly scoped commands
                ls_cmd = "vercel ls --json --limit 1"
                if vercel_token:
                    ls_cmd += f" --token={vercel_token}"
                if vercel_org_id:
                    ls_cmd += f" --scope {vercel_org_id}"

                # Get the most recent deployment
                success_ls, ls_output = self.run_command(ls_cmd, check=False)
                if success_ls:
                    try:
                        deployments = json.loads(ls_output)
                        if deployments.get("deployments"):
                            deployment_url = deployments["deployments"][0].get("url")
                            if deployment_url:
                                self.deployment_url = f"https://{deployment_url}"
                    except json.JSONDecodeError:
                        # Fallback: parse text output
                        if "https://" in ls_output:
                            for line in ls_output.split("\n"):
                                if "https://" in line and "vercel.app" in line:
                                    self.deployment_url = line.strip()
                                    break

            self.print_success("Deployment successful")
            if self.deployment_url:
                print(f"\n{Colors.MAGENTA}🌐 Deployment URL:{Colors.NC}")
                print(f"   {Colors.BLUE}{self.deployment_url}{Colors.NC}")

            self.report["deployment_method"] = "vercel_cli"
            self.report["deployment_url"] = self.deployment_url

            return True
        else:
            print(f" {Colors.RED}[FAILED]{Colors.NC}")
            self.print_error(f"Deployment failed: {output}")
            return False

    def monitor_deployment(self, timeout: int = 600):
        """Monitor deployment progress"""
        self.print_header("MONITORING DEPLOYMENT")

        start = time.time()
        dots = 0

        # Try to use GitHub API if token is available
        github_token = os.environ.get("GITHUB_TOKEN")

        # Different monitoring strategy based on deployment method
        if self.deployment_method == "github":
            actions_url = f"https://github.com/{self.org_name}/{self.repo_name}/actions"

            if github_token:
                # Poll GitHub API for deployment status
                self.print_info("Monitoring deployment via GitHub API...")
                api_url = (
                    f"https://api.github.com/repos/{self.org_name}/{self.repo_name}/deployments"
                )
                headers = {"Authorization": f"token {github_token}"}

                # Exponential backoff settings
                poll_interval = 5  # Start at 5 seconds
                max_poll_interval = 60  # Max 60 seconds between polls

                while time.time() - start < timeout:
                    try:
                        # Check for rate limiting
                        response = requests.get(
                            api_url,
                            headers=headers,
                            params={"environment": "production", "per_page": 5},
                        )

                        # Handle rate limiting
                        if response.status_code == 403:
                            remaining = response.headers.get("X-RateLimit-Remaining", "0")
                            if remaining == "0":
                                self.print_warning("GitHub API rate limit reached. Backing off...")
                                time.sleep(60)  # Wait a minute
                                continue

                        if response.status_code == 200:
                            deployments = response.json()

                            # Check each deployment (most recent first)
                            for deployment in deployments:
                                deployment_id = deployment["id"]
                                # Get deployment status
                                status_url = f"{api_url}/{deployment_id}/statuses"
                                status_response = requests.get(
                                    status_url, headers=headers, params={"per_page": 1}
                                )

                                if status_response.status_code == 200:
                                    statuses = status_response.json()
                                    if statuses:
                                        latest_status = statuses[0]
                                        if latest_status["state"] == "success":
                                            self.deployment_url = latest_status.get(
                                                "environment_url"
                                            )
                                            if self.deployment_url:
                                                self.print_success(
                                                    f"Deployment successful! URL: {self.deployment_url}"
                                                )
                                                self.report["deployment_url"] = self.deployment_url
                                                return True
                                        elif latest_status["state"] in ["error", "failure"]:
                                            self.print_error(
                                                f"Deployment failed: {latest_status.get('description', 'Unknown error')}"
                                            )
                                            return False
                                        # If in_progress or queued, continue monitoring

                        # Fallback to Workflow Runs API if Deployments API lacks info
                        if not self.deployment_url:
                            workflow_url = f"https://api.github.com/repos/{self.org_name}/{self.repo_name}/actions/runs"
                            workflow_response = requests.get(
                                workflow_url, headers=headers, params={"per_page": 1}
                            )
                            if workflow_response.status_code == 200:
                                runs = workflow_response.json().get("workflow_runs", [])
                                if runs:
                                    latest_run = runs[0]
                                    if latest_run["status"] == "completed":
                                        if latest_run["conclusion"] == "success":
                                            self.print_info(
                                                "Workflow completed successfully but deployment URL not found in API"
                                            )
                                            self.print_info(
                                                "Check GitHub Actions logs for deployment URL"
                                            )
                                        else:
                                            self.print_error(
                                                f"Workflow failed: {latest_run['conclusion']}"
                                            )
                                            return False

                    except requests.exceptions.RequestException as e:
                        self.print_warning(f"GitHub API polling error: {str(e)}")

                    # Exponential backoff
                    time.sleep(poll_interval)
                    poll_interval = min(poll_interval * 1.5, max_poll_interval)
                    print(".", end="", flush=True)
                    dots += 1
                    if dots >= 30:
                        print("")  # New line after 30 dots
                        dots = 0

                # Timeout reached
                self.print_warning(f"Deployment monitoring timed out after {timeout} seconds")
                self.print_info("Check GitHub Actions or Vercel dashboard for deployment status")
                return False

            else:
                # No GitHub token - check if we can use scoped CLI fallback
                vercel_token = os.environ.get("VERCEL_TOKEN")
                vercel_org_id = os.environ.get("VERCEL_ORG_ID")

                if not vercel_token or not vercel_org_id:
                    # Cannot use CLI fallback without proper scoping - return manual instructions
                    self.print_warning(
                        "No GitHub token found. Set GITHUB_TOKEN environment variable for automatic monitoring."
                    )
                    self.report["warnings"].append(
                        "GitHub API monitoring unavailable - no token provided"
                    )
                    if not vercel_token:
                        self.report["warnings"].append(
                            "Vercel CLI fallback unavailable - no VERCEL_TOKEN"
                        )
                    if not vercel_org_id:
                        self.report["warnings"].append(
                            "Vercel CLI fallback unavailable - no VERCEL_ORG_ID"
                        )

                    print(f"{Colors.CYAN}Monitor deployment at: {actions_url}{Colors.NC}")
                    print(f"\n{Colors.YELLOW}Manual monitoring required:{Colors.NC}")
                    print(f"1. Check deployment status at: {actions_url}")
                    print("2. Get deployment URL from GitHub Actions logs")
                    print(
                        f"3. Or check Vercel dashboard: https://vercel.com/{self.org_name.lower()}"
                    )
                    return False

                # We have both token and org ID - attempt scoped CLI fallback
                self.print_info(
                    "GitHub token not available, attempting scoped Vercel CLI fallback..."
                )

                # Check for project ID from .vercel/project.json
                expected_project_id = os.environ.get("VERCEL_PROJECT_ID")
                vercel_config_path = Path(".vercel/project.json")

                if vercel_config_path.exists():
                    try:
                        with open(vercel_config_path, "r") as f:
                            vercel_config = json.load(f)
                            if not expected_project_id:
                                expected_project_id = vercel_config.get("projectId")
                    except Exception as e:
                        self.print_warning(f"Could not read Vercel config: {str(e)}")

                # Monitor with scoped CLI
                print(
                    f"{Colors.YELLOW}Monitoring deployment via scoped Vercel CLI{Colors.NC}",
                    end="",
                    flush=True,
                )
                start = time.time()
                dots = 0
                timeout = 300  # 5 minutes for CLI fallback

                while time.time() - start < timeout:
                    print(".", end="", flush=True)
                    dots += 1
                    if dots >= 30:
                        print("")  # New line after 30 dots
                        dots = 0
                    time.sleep(5)

                    # Build properly scoped command
                    ls_cmd = (
                        f"vercel ls --limit 5 --json --token={vercel_token} --scope {vercel_org_id}"
                    )
                    success, output = self.run_command(ls_cmd, check=False)

                    if success:
                        try:
                            deployments_data = json.loads(output)
                            deployments = deployments_data.get("deployments", [])

                            # Find deployment matching our project
                            for deployment in deployments:
                                deployment_project = deployment.get("projectId") or deployment.get(
                                    "project"
                                )
                                deployment_org = deployment.get("ownerId") or deployment.get(
                                    "orgId"
                                )

                                # Verify this deployment belongs to our project and org
                                if deployment_org == vercel_org_id:
                                    if expected_project_id:
                                        # We have a project ID - match exactly
                                        if deployment_project == expected_project_id:
                                            self.deployment_url = f"https://{deployment['url']}"
                                            self.print_success(
                                                f"\nDeployment detected via scoped CLI: {self.deployment_url}"
                                            )
                                            self.report["deployment_url"] = self.deployment_url
                                            return True
                                    else:
                                        # No project ID but org matches - take first matching deployment
                                        self.deployment_url = f"https://{deployment['url']}"
                                        self.print_warning(
                                            f"\nDeployment detected (org-scoped only): {self.deployment_url}"
                                        )
                                        self.report["deployment_url"] = self.deployment_url
                                        self.report["warnings"].append(
                                            "Project ID not available for exact matching"
                                        )
                                        return True

                        except json.JSONDecodeError:
                            self.print_warning("Could not parse Vercel CLI output")

                # Timeout reached without finding deployment
                self.print_warning(f"\nCLI monitoring timed out after {timeout} seconds")
                print(f"{Colors.CYAN}Monitor deployment at: {actions_url}{Colors.NC}")
                print(f"\n{Colors.YELLOW}Manual monitoring required:{Colors.NC}")
                print(f"1. Check deployment status at: {actions_url}")
                print("2. Get deployment URL from GitHub Actions logs")
                print(
                    f"3. Or check Vercel dashboard: https://vercel.com/{vercel_org_id or self.org_name.lower()}"
                )
                return False

        # Vercel CLI deployment method
        elif self.deployment_method == "vercel":
            # Get environment variables for proper scoping
            vercel_token = os.environ.get("VERCEL_TOKEN")
            vercel_org_id = os.environ.get("VERCEL_ORG_ID")
            vercel_project_id = os.environ.get("VERCEL_PROJECT_ID")

            # Check for .vercel/project.json to get project info
            expected_project_id = vercel_project_id
            expected_org_id = vercel_org_id

            vercel_config_path = Path(".vercel/project.json")
            if vercel_config_path.exists():
                try:
                    with open(vercel_config_path, "r") as f:
                        vercel_config = json.load(f)
                        config_org_id = vercel_config.get("orgId")
                        config_project_id = vercel_config.get("projectId")

                        # Use config values if env vars not set
                        if not expected_org_id:
                            expected_org_id = config_org_id
                        if not expected_project_id:
                            expected_project_id = config_project_id

                        self.print_info(
                            f"Monitoring project: {config_project_id} (org: {config_org_id})"
                        )
                except Exception as e:
                    self.print_warning(f"Could not read Vercel config: {str(e)}")

            if not expected_org_id:
                self.print_warning(
                    "No VERCEL_ORG_ID found. Deployment monitoring may target wrong organization."
                )
                self.print_info("Set VERCEL_ORG_ID environment variable for proper scoping.")
                return False

            print(f"{Colors.YELLOW}Deployment in progress{Colors.NC}", end="", flush=True)

            while time.time() - start < timeout:
                print(".", end="", flush=True)
                dots += 1
                if dots >= 30:
                    print("")  # New line after 30 dots
                    dots = 0
                time.sleep(5)

                # Try to get deployment URL from Vercel with proper scoping
                if not self.deployment_url and self.vercel_cli_available:
                    # Build properly scoped command
                    ls_cmd = "vercel ls --limit 1 --json"
                    if vercel_token:
                        ls_cmd += f" --token={vercel_token}"
                    if expected_org_id:
                        ls_cmd += f" --scope {expected_org_id}"

                    success, output = self.run_command(ls_cmd, check=False)
                    if success:
                        try:
                            deployments_data = json.loads(output)
                            deployments = deployments_data.get("deployments", [])

                            # Find deployment matching our project
                            for deployment in deployments:
                                # Check if deployment belongs to expected project
                                deployment_project = deployment.get("projectId") or deployment.get(
                                    "project"
                                )
                                deployment_org = deployment.get("ownerId") or deployment.get(
                                    "orgId"
                                )

                                # Verify this deployment belongs to our project
                                if expected_project_id:
                                    if deployment_project == expected_project_id:
                                        self.deployment_url = f"https://{deployment['url']}"
                                        break
                                elif expected_org_id:
                                    # At minimum verify org matches
                                    if deployment_org == expected_org_id:
                                        self.deployment_url = f"https://{deployment['url']}"
                                        break
                                else:
                                    # Last resort - take first deployment but warn
                                    self.deployment_url = f"https://{deployment['url']}"
                                    self.print_warning(
                                        "Deployment URL detected but could not verify project/org ownership"
                                    )
                                    break

                        except json.JSONDecodeError:
                            self.print_warning("Could not parse Vercel CLI output")

                if self.deployment_url:
                    print(
                        f"\n{Colors.GREEN}✅ Deployment URL detected: {self.deployment_url}{Colors.NC}"
                    )
                    break

            if self.deployment_url:
                self.report["deployment_url"] = self.deployment_url
                return True
            else:
                print(
                    f"\n{Colors.YELLOW}⚠️  Could not detect deployment URL automatically{Colors.NC}"
                )
                print(
                    f"Check Vercel dashboard: https://vercel.com/{expected_org_id or self.org_name.lower()}"
                )
                return False

        # Default case - shouldn't normally reach here
        print(f"\n{Colors.YELLOW}⚠️  Unknown deployment method: {self.deployment_method}{Colors.NC}")
        return False

    def validate_deployment(self, url: Optional[str] = None) -> bool:
        """Validate the deployed application"""
        self.print_header("POST-DEPLOYMENT VALIDATION")

        if not url:
            url = self.deployment_url

        if not url:
            self.print_warning("No deployment URL available for validation")
            self.print_info("Please check GitHub Actions or Vercel dashboard for deployment status")
            return False

        validation_results = []
        validation_details = []  # For detailed reporting

        # Health check endpoints - added database connectivity check
        endpoints = {
            "/health": "Basic health check",
            "/ready": "Readiness check",
            "/api/v1/health/detailed": "Detailed health status",
            "/api/v1/health/database": "Database connectivity",
        }

        for endpoint, description in endpoints.items():
            self.print_progress(f"Checking {description}")
            detail = {
                "endpoint": endpoint,
                "description": description,
                "status": "unknown",
                "http_status": None,
                "error": None,
            }

            try:
                response = requests.get(f"{url}{endpoint}", timeout=10)
                detail["http_status"] = response.status_code

                if response.status_code == 200:
                    print(f" {Colors.GREEN}[OK]{Colors.NC}")
                    validation_results.append(True)
                    detail["status"] = "success"
                else:
                    print(f" {Colors.YELLOW}[{response.status_code}]{Colors.NC}")
                    validation_results.append(False)
                    detail["status"] = "failed"
                    detail["error"] = f"HTTP {response.status_code}"
            except Exception as e:
                print(f" {Colors.RED}[ERROR]{Colors.NC}")
                self.print_error(f"Failed to check {endpoint}: {str(e)}")
                validation_results.append(False)
                detail["status"] = "error"
                detail["error"] = str(e)

            validation_details.append(detail)

        # API documentation
        self.print_progress("Checking API documentation")
        detail = {
            "endpoint": "/docs",
            "description": "API documentation",
            "status": "unknown",
            "http_status": None,
            "error": None,
        }

        try:
            response = requests.get(f"{url}/docs", timeout=10)
            detail["http_status"] = response.status_code

            if response.status_code == 200:
                print(f" {Colors.GREEN}[AVAILABLE]{Colors.NC}")
                validation_results.append(True)
                detail["status"] = "success"
            else:
                print(f" {Colors.YELLOW}[{response.status_code}]{Colors.NC}")
                validation_results.append(False)
                detail["status"] = "failed"
                detail["error"] = f"HTTP {response.status_code}"
        except Exception as e:
            print(f" {Colors.RED}[ERROR]{Colors.NC}")
            validation_results.append(False)
            detail["status"] = "error"
            detail["error"] = str(e)

        validation_details.append(detail)

        # Store validation details in report
        self.report["validation_details"] = validation_details

        # Overall validation result
        if all(validation_results):
            self.print_success("All validation checks passed")
            self.report["validation"] = "passed"
            return True
        elif any(validation_results):
            self.print_warning("Some validation checks failed")
            self.report["validation"] = "partial"
            return True
        else:
            self.print_error("All validation checks failed")
            self.report["validation"] = "failed"
            return False

    def generate_deployment_report(self):
        """Generate and save deployment report"""
        self.print_header("DEPLOYMENT REPORT")

        # Calculate deployment time
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        self.report["end_time"] = end_time.isoformat()
        self.report["duration_seconds"] = duration
        self.report["status"] = "completed"

        # Save report
        report_file = Path(f"deployment_report_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_file, "w") as f:
            json.dump(self.report, f, indent=2)

        self.print_success(f"Report saved: {report_file}")

        # Print summary
        print(f"\n{Colors.BOLD}Deployment Summary:{Colors.NC}")
        print(f"  Environment: {Colors.CYAN}{self.environment}{Colors.NC}")
        print(f"  Duration: {Colors.CYAN}{duration:.1f} seconds{Colors.NC}")
        print(f"  Method: {Colors.CYAN}{self.report.get('deployment_method', 'N/A')}{Colors.NC}")

        if self.deployment_url:
            print(f"  URL: {Colors.BLUE}{self.deployment_url}{Colors.NC}")

        if self.report.get("validation") == "passed":
            print(f"  Validation: {Colors.GREEN}✅ Passed{Colors.NC}")
        elif self.report.get("validation") == "partial":
            print(f"  Validation: {Colors.YELLOW}⚠️  Partial{Colors.NC}")
        else:
            print(f"  Validation: {Colors.RED}❌ Failed{Colors.NC}")

        if self.report["errors"]:
            print(f"\n{Colors.RED}Errors:{Colors.NC}")
            for error in self.report["errors"]:
                print(f"  • {error}")

        if self.report["warnings"]:
            print(f"\n{Colors.YELLOW}Warnings:{Colors.NC}")
            for warning in self.report["warnings"]:
                print(f"  • {warning}")

    def run(self, method: str = "auto") -> int:
        """Execute the deployment"""
        print(f"{Colors.BOLD}{Colors.MAGENTA}")
        print("🚀 ruleIQ ORGANIZATION DEPLOYMENT EXECUTOR")
        print(f"Environment: {self.environment}")
        print(f"{Colors.NC}")

        # Pre-deployment validation
        if not self.pre_deployment_validation():
            self.print_error("Pre-deployment validation failed")
            if self.non_interactive:
                # Choose default: abort is safer for CI
                self.print_error("Exiting due to validation failure in non-interactive mode")
                return 1
            resp = input("\nContinue anyway? (y/N): ").strip().lower()
            if resp != "y":
                return 1

        # Execute deployment based on method
        deployment_success = False

        if method in {"auto", "github"}:
            deployment_success = self.trigger_github_actions_deployment()
            if deployment_success:
                self.monitor_deployment()
        elif method == "vercel":
            deployment_success = self.trigger_vercel_cli_deployment()
            if deployment_success:
                self.monitor_deployment()
        else:
            self.print_error(f"Unknown deployment method: {method}")
            return 1

        if not deployment_success:
            self.print_error("Deployment failed")
            self.generate_deployment_report()
            return 1

        # Post-deployment validation
        validation_ok = None  # Track validation result explicitly
        if self.non_interactive:
            if self.deployment_url:
                validation_ok = self.validate_deployment(self.deployment_url)
            else:
                self.print_info(
                    "No deployment URL detected - skipping validation in non-interactive mode"
                )
                self.print_info("Check deployment status at GitHub Actions or Vercel dashboard")
                validation_ok = None  # No validation performed
        else:
            # Fix double-prompt bug: capture once and reuse value
            if not self.deployment_url:
                entered = input(
                    "\nEnter deployment URL for validation (or press Enter to skip): "
                ).strip()
                validation_url = entered
            else:
                validation_url = self.deployment_url

            if validation_url:
                # Check if validate-deployment.sh exists and offer to use it
                validate_script = Path("scripts/deploy/validate-deployment.sh")
                if validate_script.exists() and validate_script.is_file():
                    use_script = (
                        input("\nUse validate-deployment.sh script? (y/N): ").lower() == "y"
                    )
                    if use_script:
                        self.print_info(f"Running validation script: {validate_script}")
                        success, output = self.run_command(
                            f"bash {validate_script} '{validation_url}'", check=False
                        )
                        print(output)
                        if success:
                            self.print_success("Validation script completed successfully")
                            validation_ok = True
                        else:
                            self.print_warning("Validation script reported issues")
                            validation_ok = False
                    else:
                        validation_ok = self.validate_deployment(validation_url)
                else:
                    validation_ok = self.validate_deployment(validation_url)
            else:
                validation_ok = None  # No validation performed

        # Enforce strict validation mode before generating report
        if self.strict_validation:
            # Prefer explicit boolean; fall back to report aggregation
            failed = (validation_ok is False) or (self.report.get("validation") == "failed")
            if failed:
                self.print_error("Strict validation enabled: failing due to validation errors")
                self.generate_deployment_report()
                return 1

        # Generate report
        self.generate_deployment_report()

        # Final status
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 DEPLOYMENT COMPLETE!{Colors.NC}")

        if self.deployment_url:
            print(f"\n{Colors.MAGENTA}Your ruleIQ application is live at:{Colors.NC}")
            print(f"   {Colors.BLUE}{Colors.BOLD}{self.deployment_url}{Colors.NC}")

        print(f"\n{Colors.CYAN}Next steps:{Colors.NC}")
        print("  1. Verify application functionality")
        print("  2. Configure custom domain (if needed)")
        print("  3. Set up monitoring and alerts")
        print("  4. Share with your team")

        return 0


def main():
    parser = argparse.ArgumentParser(description="Execute ruleIQ organization deployment")
    parser.add_argument(
        "--environment",
        choices=["production", "preview"],
        default="production",
        help="Deployment environment",
    )
    parser.add_argument(
        "--method",
        choices=["auto", "github", "vercel"],
        default="auto",
        help="Deployment method (auto will try GitHub Actions first)",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Non-interactive mode - skip all prompts and proceed with defaults",
    )
    parser.add_argument(
        "--strict-validation",
        action="store_true",
        help="Exit with non-zero code if validation fails",
    )
    parser.add_argument(
        "--require-org-remote",
        action="store_true",
        help="Require connection to organization repository (for CI)",
    )

    args = parser.parse_args()

    executor = DeploymentExecutor(
        environment=args.environment,
        non_interactive=args.yes,
        strict_validation=args.strict_validation,
        require_org_remote=args.require_org_remote,
    )
    sys.exit(executor.run(method=args.method))


if __name__ == "__main__":
    main()
