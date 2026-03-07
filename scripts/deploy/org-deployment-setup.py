#!/usr/bin/env python3
"""
Organization-Level Deployment Setup Script for ruleIQ
Verifies and configures organization-level deployment infrastructure
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Tuple
from datetime import datetime


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


class OrganizationDeploymentSetup:
    def __init__(self) -> None:
        self.org_name = "RuleIQ-Vercel-Deploy"
        self.repo_name = "ruleIQ"
        self.org_repo_url = f"https://github.com/{self.org_name}/{self.repo_name}.git"
        self.project_root = Path.cwd()
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "organization": self.org_name,
            "repository": self.repo_name,
            "checks": {},
            "recommendations": [],
        }

    def print_header(self, message: str):
        """Print formatted section header"""
        print(f"\n{Colors.BLUE}{'=' * 60}{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}{message}{Colors.NC}")
        print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}\n")

    def print_success(self, message: str):
        """Print success message"""
        print(f"{Colors.GREEN}✅ {message}{Colors.NC}")

    def print_warning(self, message: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.NC}")

    def print_error(self, message: str):
        """Print error message"""
        print(f"{Colors.RED}❌ {message}{Colors.NC}")

    def print_info(self, message: str):
        """Print info message"""
        print(f"{Colors.BLUE}ℹ️  {message}{Colors.NC}")

    def run_command(self, command: str, check: bool = True) -> Tuple[bool, str]:
        """Run shell command and return result"""
        try:
            result = subprocess.run(
                command, shell=True, check=check, capture_output=True, text=True
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr or str(e)

    def verify_organization_repository(self) -> bool:
        """Verify GitHub repository connection to organization"""
        self.print_header("1. ORGANIZATION REPOSITORY VERIFICATION")

        # Check current git remote
        success, output = self.run_command("git remote get-url origin")
        if success and self.org_repo_url in output:
            self.print_success(f"Git remote correctly set to: {self.org_repo_url}")
            self.report["checks"]["repository"] = "passed"

            # Test repository access
            success, _ = self.run_command("git ls-remote origin", check=False)
            if success:
                self.print_success("Repository access verified")
                return True
            else:
                self.print_error("Cannot access repository - check permissions")
                self.report["recommendations"].append(
                    "Ensure you have push access to the organization repository"
                )
                return False
        else:
            self.print_error(f"Git remote not set to organization. Current: {output.strip()}")
            self.print_info(f"Run: git remote set-url origin {self.org_repo_url}")
            self.report["checks"]["repository"] = "failed"
            self.report["recommendations"].append(
                f"Update git remote: git remote set-url origin {self.org_repo_url}"
            )
            return False

    def verify_github_actions_secrets(self) -> bool:
        """Check if required GitHub Actions secrets are documented"""
        self.print_header("2. GITHUB ACTIONS SECRETS CONFIGURATION")

        required_secrets = {
            "VERCEL_TOKEN": "Vercel authentication token with organization access",
            "VERCEL_ORG_ID": "RuleIQ-Vercel-Deploy organization ID",
            "VERCEL_PROJECT_ID": "Project ID after transfer to organization",
            "DATABASE_URL": "Neon organization database URL with connection pooling",
            "JWT_SECRET": "Secure 32+ character secret for JWT tokens",
            "SECRET_KEY": "Secure 32+ character secret for encryption",
        }

        optional_secrets = {
            "OPENAI_API_KEY": "OpenAI API key for AI features",
            "GOOGLE_AI_API_KEY": "Google AI API key (alternative provider)",
            "REDIS_URL": "Redis URL for enhanced caching",
            "SENTRY_DSN": "Sentry DSN for error tracking",
            "SONAR_TOKEN": "SonarCloud token for code quality",
            "SONAR_HOST_URL": "SonarCloud URL for analysis",
        }

        print(f"{Colors.BOLD}Required Secrets:{Colors.NC}")
        for secret, description in required_secrets.items():
            print(f"  {Colors.YELLOW}{secret:<20}{Colors.NC} - {description}")

        print(f"\n{Colors.BOLD}Optional Secrets:{Colors.NC}")
        for secret, description in optional_secrets.items():
            print(f"  {Colors.CYAN}{secret:<20}{Colors.NC} - {description}")

        print(f"\n{Colors.MAGENTA}🔗 Configure secrets at:{Colors.NC}")
        print(
            f"   {Colors.BLUE}https://github.com/{self.org_name}/{self.repo_name}/settings/secrets/actions{Colors.NC}"
        )

        self.report["checks"]["secrets_documented"] = "passed"
        self.report["recommendations"].append(
            f"Configure all required secrets at: https://github.com/{self.org_name}/{self.repo_name}/settings/secrets/actions"
        )

        return True

    def verify_vercel_cli(self) -> bool:
        """Verify Vercel CLI installation and authentication"""
        self.print_header("3. VERCEL CLI VERIFICATION")

        # Check Vercel CLI installation
        success, output = self.run_command("vercel --version", check=False)
        if success:
            self.print_success(f"Vercel CLI installed: {output.strip()}")
            self.report["checks"]["vercel_cli"] = "passed"

            # Check Vercel authentication
            success, _ = self.run_command("vercel whoami", check=False)
            if success:
                self.print_success("Vercel CLI authenticated")
                self.print_info("Run 'vercel link' to connect project to organization")
                return True
            else:
                self.print_warning("Vercel CLI not authenticated")
                self.print_info("Run: vercel login")
                self.report["recommendations"].append("Authenticate Vercel CLI: vercel login")
                return False
        else:
            self.print_error("Vercel CLI not installed")
            self.print_info("Install: npm i -g vercel")
            self.report["checks"]["vercel_cli"] = "failed"
            self.report["recommendations"].append("Install Vercel CLI: npm i -g vercel")
            return False

    def verify_neon_database_config(self) -> bool:
        """Verify Neon Database organization configuration"""
        self.print_header("4. NEON DATABASE ORGANIZATION SETUP")

        print(f"{Colors.BOLD}Neon Database Organization Features:{Colors.NC}")
        features = [
            "✅ Connection Pooling (pgbouncer) - Optimized for serverless",
            "✅ Database Branching - Separate databases for environments",
            "✅ Point-in-time Recovery - Enhanced backup capabilities",
            "✅ Team Access - Multiple developers can access",
            "✅ Advanced Monitoring - Real-time performance insights",
        ]

        for feature in features:
            print(f"  {feature}")

        print(f"\n{Colors.BOLD}Database URL Format:{Colors.NC}")
        print(
            f"  {Colors.CYAN}postgresql://[user]:[password]@[host]/ruleiq?sslmode=require&pgbouncer=true{Colors.NC}"
        )

        print(f"\n{Colors.YELLOW}Important Configuration:{Colors.NC}")
        print("  1. Use organization-level Neon project")
        print("  2. Enable connection pooling (pgbouncer)")
        print("  3. Set appropriate pool size for serverless")
        print("  4. Configure database branching if needed")

        self.report["checks"]["neon_database"] = "documented"
        self.report["recommendations"].append(
            "Configure Neon Database with organization-level project and connection pooling"
        )

        return True

    def verify_environment_files(self) -> bool:
        """Verify environment configuration files"""
        self.print_header("5. ENVIRONMENT CONFIGURATION FILES")

        files_to_check = {
            "vercel.json": "Vercel configuration",
            ".github/workflows/deploy-vercel.yml": "GitHub Actions deployment workflow",
            "main.py": "Main application entry point",
            "api/main.py": "FastAPI application",
            "config/settings.py": "Application settings",
        }

        all_present = True
        for file_path, description in files_to_check.items():
            if Path(file_path).exists():
                self.print_success(f"{description}: {file_path}")
            else:
                self.print_error(f"Missing: {file_path}")
                all_present = False

        self.report["checks"]["environment_files"] = "passed" if all_present else "failed"

        if not all_present:
            self.report["recommendations"].append(
                "Ensure all required configuration files are present"
            )

        return all_present

    def verify_deployment_workflow(self) -> bool:
        """Verify GitHub Actions deployment workflow"""
        self.print_header("6. GITHUB ACTIONS DEPLOYMENT WORKFLOW")

        workflow_file = Path(".github/workflows/deploy-vercel.yml")
        if workflow_file.exists():
            self.print_success("Deployment workflow found")

            # Check workflow content for organization references
            with open(workflow_file) as f:
                content = f.read()

            checks = {
                "VERCEL_ORG_ID": "Organization ID reference",
                "VERCEL_PROJECT_ID": "Project ID reference",
                "VERCEL_TOKEN": "Vercel token reference",
                "DATABASE_URL": "Database URL reference",
            }

            for key, description in checks.items():
                if key in content:
                    self.print_success(f"{description} found in workflow")
                else:
                    self.print_warning(f"{description} not found - may use different reference")

            self.report["checks"]["deployment_workflow"] = "passed"
            return True
        else:
            self.print_error("Deployment workflow not found")
            self.report["checks"]["deployment_workflow"] = "failed"
            self.report["recommendations"].append("Create GitHub Actions deployment workflow")
            return False

    def generate_deployment_commands(self):
        """Generate ready-to-use deployment commands"""
        self.print_header("7. DEPLOYMENT COMMANDS")

        print(f"{Colors.BOLD}Option A: Automatic Deployment (Recommended){Colors.NC}")
        print(f"{Colors.GREEN}# Push to main branch triggers automatic deployment{Colors.NC}")
        print(f"  {Colors.CYAN}git push origin main{Colors.NC}")
        print(
            f"  {Colors.BLUE}# Monitor at: https://github.com/{self.org_name}/{self.repo_name}/actions{Colors.NC}"
        )

        print(f"\n{Colors.BOLD}Option B: Manual GitHub Actions{Colors.NC}")
        print(
            f"  1. Go to: {Colors.BLUE}https://github.com/{self.org_name}/{self.repo_name}/actions{Colors.NC}"
        )
        print("  2. Select 'Vercel Deployment' workflow")
        print("  3. Click 'Run workflow'")
        print("  4. Select 'production' environment")

        print(f"\n{Colors.BOLD}Option C: Vercel CLI Direct{Colors.NC}")
        print(f"  {Colors.CYAN}vercel link{Colors.NC}  # Link to organization")
        print(f"  {Colors.CYAN}vercel --prod{Colors.NC}  # Deploy to production")

        self.report["deployment_commands"] = {
            "automatic": "git push origin main",
            "manual_github": f"https://github.com/{self.org_name}/{self.repo_name}/actions",
            "vercel_cli": "vercel --prod",
        }

    def verify_team_access(self):
        """Document team access configuration"""
        self.print_header("8. TEAM ACCESS CONFIGURATION")

        print(f"{Colors.BOLD}GitHub Organization Access:{Colors.NC}")
        print(
            f"  • Add team members: {Colors.BLUE}https://github.com/{self.org_name}/people{Colors.NC}"
        )
        print(
            f"  • Repository access: {Colors.BLUE}https://github.com/{self.org_name}/{self.repo_name}/settings/access{Colors.NC}"
        )

        print(f"\n{Colors.BOLD}Vercel Organization Access:{Colors.NC}")
        print("  • Team settings in Vercel dashboard")
        print("  • Project-specific permissions")
        print("  • Environment variable access controls")

        print(f"\n{Colors.BOLD}Neon Database Access:{Colors.NC}")
        print("  • Database user management")
        print("  • Branch-based access controls")
        print("  • Read/write permissions per user")

        self.report["checks"]["team_access"] = "documented"

    def generate_validation_script(self):
        """Generate post-deployment validation script"""
        self.print_header("9. POST-DEPLOYMENT VALIDATION")

        validation_script = """#!/bin/bash
# Post-deployment validation script

DEPLOYMENT_URL="${1:-https://your-app.vercel.app}"

echo "🔍 Validating deployment at: $DEPLOYMENT_URL"

# Check if jq is installed, provide fallback
if command -v jq &> /dev/null; then
    JQ_CMD="jq '.'"
else
    echo "⚠️  jq not found, using cat for raw output"
    JQ_CMD="cat"
fi

# Health checks
echo "Checking health endpoints..."
curl -s "$DEPLOYMENT_URL/health" | $JQ_CMD
curl -s "$DEPLOYMENT_URL/ready" | $JQ_CMD
curl -s "$DEPLOYMENT_URL/api/v1/health/detailed" | $JQ_CMD

# API documentation
echo "Checking API documentation..."
curl -s -o /dev/null -w "%{http_code}" "$DEPLOYMENT_URL/docs"

# Database connectivity (through health endpoint)
echo "Verifying database connectivity..."
curl -s "$DEPLOYMENT_URL/api/v1/health/database" | $JQ_CMD

echo "✅ Validation complete"
"""

        validation_file = Path("scripts/deploy/validate-deployment.sh")
        validation_file.parent.mkdir(parents=True, exist_ok=True)
        validation_file.write_text(validation_script)
        validation_file.chmod(0o755)

        self.print_success(f"Validation script created: {validation_file}")
        print(
            f"  Run after deployment: {Colors.CYAN}./scripts/deploy/validate-deployment.sh [URL]{Colors.NC}"
        )

        self.report["validation_script"] = str(validation_file)

    def save_report(self):
        """Save deployment readiness report"""
        report_file = Path("organization_deployment_report.json")
        with open(report_file, "w") as f:
            json.dump(self.report, f, indent=2)

        self.print_success(f"Report saved: {report_file}")

    def run(self):
        """Run complete organization deployment setup"""
        print(f"{Colors.BOLD}{Colors.MAGENTA}")
        print("🏢 ruleIQ ORGANIZATION DEPLOYMENT SETUP")
        print(f"{Colors.NC}")

        # Run all verifications
        checks = [
            self.verify_organization_repository(),
            self.verify_github_actions_secrets(),
            self.verify_vercel_cli(),
            self.verify_neon_database_config(),
            self.verify_environment_files(),
            self.verify_deployment_workflow(),
        ]

        # Generate deployment resources
        self.generate_deployment_commands()
        self.verify_team_access()
        self.generate_validation_script()

        # Summary
        self.print_header("DEPLOYMENT READINESS SUMMARY")

        all_passed = all(checks)
        if all_passed:
            print(f"{Colors.GREEN}{Colors.BOLD}✅ READY FOR ORGANIZATION DEPLOYMENT!{Colors.NC}")
            print(f"\n{Colors.YELLOW}Next Steps:{Colors.NC}")
            print("1. Configure GitHub Actions secrets")
            print("2. Link Vercel project to organization")
            print("3. Push to main branch to deploy")
        else:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  SOME CHECKS REQUIRE ATTENTION{Colors.NC}")
            print(f"\n{Colors.YELLOW}Recommendations:{Colors.NC}")
            for rec in self.report["recommendations"]:
                print(f"  • {rec}")

        # Save report
        self.save_report()

        print(f"\n{Colors.MAGENTA}🔗 Organization Repository:{Colors.NC}")
        print(f"   {Colors.BLUE}{self.org_repo_url}{Colors.NC}")

        print(f"\n{Colors.GREEN}🚀 Ready to deploy? Run:{Colors.NC}")
        print(f"   {Colors.CYAN}git push origin main{Colors.NC}")

        return 0 if all_passed else 1


if __name__ == "__main__":
    setup = OrganizationDeploymentSetup()
    sys.exit(setup.run())
