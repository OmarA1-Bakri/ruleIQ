#!/usr/bin/env python3
"""
Branch Cleanup - Manage local and remote branches after PR processing
"""

import subprocess
import json
from typing import List, Dict
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class BranchCleanup:
    """Handles branch cleanup operations"""

    def __init__(self, dry_run: bool = True) -> None:
        """Initialize branch cleanup"""
        self.dry_run = dry_run
        self.protected_branches = ["main", "master", "develop", "staging", "production"]

    def cleanup_merged_branches(self) -> Dict:
        """Clean up merged branches"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "local_deleted": [],
            "remote_deleted": [],
            "skipped": [],
            "errors": [],
        }

        # Get merged branches
        merged_local = self._get_merged_branches(remote=False)
        merged_remote = self._get_merged_branches(remote=True)

        # Clean local branches
        for branch in merged_local:
            if branch not in self.protected_branches:
                if self._delete_local_branch(branch):
                    results["local_deleted"].append(branch)
                else:
                    results["errors"].append(f"Failed to delete local branch: {branch}")
            else:
                results["skipped"].append(f"Protected branch: {branch}")

        # Clean remote branches
        for branch in merged_remote:
            if branch not in self.protected_branches:
                if self._delete_remote_branch(branch):
                    results["remote_deleted"].append(branch)
                else:
                    results["errors"].append(f"Failed to delete remote branch: {branch}")

        return results

    def _get_merged_branches(self, remote: bool = False) -> List[str]:
        """Get list of merged branches"""
        try:
            if remote:
                cmd = ["git", "branch", "-r", "--merged", "origin/main"]
            else:
                cmd = ["git", "branch", "--merged", "main"]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            branches = [
                b.strip().replace("origin/", "")
                for b in result.stdout.splitlines()
                if b.strip() and not b.strip().startswith("*")
            ]
            return branches
        except subprocess.CalledProcessError as e:
            logger.error(f"Error getting merged branches: {e}")
            return []

    def _delete_local_branch(self, branch: str) -> bool:
        """Delete a local branch"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete local branch: {branch}")
            return True

        try:
            subprocess.run(["git", "branch", "-d", branch], check=True, capture_output=True)
            logger.info(f"Deleted local branch: {branch}")
            return True
        except subprocess.CalledProcessError:
            try:
                subprocess.run(["git", "branch", "-D", branch], check=True, capture_output=True)
                logger.info(f"Force deleted local branch: {branch}")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to delete local branch {branch}: {e}")
                return False

    def _delete_remote_branch(self, branch: str) -> bool:
        """Delete a remote branch"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete remote branch: {branch}")
            return True

        try:
            subprocess.run(
                ["git", "push", "origin", "--delete", branch], check=True, capture_output=True
            )
            logger.info(f"Deleted remote branch: {branch}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to delete remote branch {branch}: {e}")
            return False

    def prune_remote_references(self) -> bool:
        """Prune stale remote references"""
        if self.dry_run:
            logger.info("[DRY RUN] Would prune remote references")
            return True

        try:
            subprocess.run(["git", "remote", "prune", "origin"], check=True)
            logger.info("Pruned stale remote references")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to prune remote references: {e}")
            return False

    def update_main_branch(self) -> bool:
        """Update main branch with latest changes"""
        if self.dry_run:
            logger.info("[DRY RUN] Would update main branch")
            return True

        try:
            # Checkout main
            subprocess.run(["git", "checkout", "main"], check=True)

            # Pull latest changes
            subprocess.run(["git", "pull", "origin", "main"], check=True)

            logger.info("Updated main branch")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update main branch: {e}")
            return False

    def generate_report(self, results: Dict) -> str:
        """Generate cleanup report"""
        report = ["# Branch Cleanup Report\n"]
        report.append(f"Generated: {results['timestamp']}\n\n")

        if results["local_deleted"]:
            report.append("## Local Branches Deleted\n")
            for branch in results["local_deleted"]:
                report.append(f"- {branch}\n")

        if results["remote_deleted"]:
            report.append("\n## Remote Branches Deleted\n")
            for branch in results["remote_deleted"]:
                report.append(f"- origin/{branch}\n")

        if results["skipped"]:
            report.append("\n## Skipped\n")
            for item in results["skipped"]:
                report.append(f"- {item}\n")

        if results["errors"]:
            report.append("\n## Errors\n")
            for error in results["errors"]:
                report.append(f"- {error}\n")

        return "".join(report)


def main():
    """Main execution function"""
    cleanup = BranchCleanup(dry_run=True)

    # Update main branch
    cleanup.update_main_branch()

    # Clean up merged branches
    results = cleanup.cleanup_merged_branches()

    # Prune remote references
    cleanup.prune_remote_references()

    # Generate report
    report = cleanup.generate_report(results)
    print(report)

    with open("branch_cleanup_report.md", "w") as f:
        f.write(report)

    with open("branch_cleanup_results.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
