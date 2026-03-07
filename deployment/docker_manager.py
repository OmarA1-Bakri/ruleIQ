#!/usr/bin/env python3
"""
Docker deployment manager for ruleIQ.
Handles containerized deployment with health checks and orchestration.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class DockerManager:
    """Docker deployment and orchestration manager."""

    def __init__(self, environment: str = "staging", compose_file: Optional[str] = None) -> None:
        """Initialize Docker manager.

        Args:
            environment: Target deployment environment
            compose_file: Path to Docker Compose file (auto-detected if not specified)
        """
        self.environment = environment
        self.compose_file = compose_file or self.get_compose_file()
        self.results: Dict[str, bool] = {}
        self.containers: List[str] = []

    def get_compose_file(self) -> str:
        """Determine appropriate Docker Compose file based on environment.

        Returns:
            Path to Docker Compose file
        """
        if self.environment == "production":
            if Path("docker-compose.prod.yml").exists():
                return "docker-compose.prod.yml"
        elif self.environment == "test" and Path("docker-compose.test.yml").exists():
            return "docker-compose.test.yml"

        # Default to base compose file
        return "docker-compose.yml"

    def log(self, message: str, level: str = "info"):
        """Log messages with formatting.

        Args:
            message: Message to log
            level: Log level (info, success, warning, error)
        """
        symbols = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌", "docker": "🐳"}

        colors = {
            "info": "\033[94m",
            "success": "\033[92m",
            "warning": "\033[93m",
            "error": "\033[91m",
            "docker": "\033[96m",
            "reset": "\033[0m",
        }

        symbol = symbols.get(level, "ℹ️")
        color = colors.get(level, colors["info"])
        print(f"{color}{symbol} {message}{colors['reset']}")

    def run_command(self, command: str, description: str) -> Tuple[bool, str]:
        """Execute a Docker command.

        Args:
            command: Command to execute
            description: Command description

        Returns:
            Tuple of (success, output)
        """
        self.log(f"Executing: {description}", "docker")

        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                self.log(f"✅ {description} completed", "success")
                return True, result.stdout
            else:
                self.log(f"❌ {description} failed", "error")
                if result.stderr:
                    print(f"Error: {result.stderr[:500]}")
                return False, result.stderr

        except Exception as e:
            self.log(f"💥 Exception during {description}: {str(e)}", "error")
            return False, str(e)

    def check_docker_installation(self) -> bool:
        """Verify Docker and Docker Compose are installed and running."""
        self.log("Checking Docker installation...")

        # Check Docker
        success, output = self.run_command("docker --version", "Docker version check")
        if not success:
            self.log("Docker is not installed or not running", "error")
            return False

        # Check Docker daemon
        success, output = self.run_command("docker ps", "Docker daemon check")
        if not success:
            self.log("Docker daemon is not running", "error")
            self.log("Please start Docker and try again", "warning")
            return False

        # Check Docker Compose
        success, output = self.run_command("docker-compose --version", "Docker Compose check")
        if not success:
            self.log("Docker Compose is not installed", "error")
            return False

        self.log("Docker installation verified", "success")
        return True

    def validate_compose_file(self) -> bool:
        """Validate Docker Compose configuration."""
        self.log(f"Validating Docker Compose file: {self.compose_file}")

        if not Path(self.compose_file).exists():
            self.log(f"Compose file {self.compose_file} not found", "error")
            return False

        # Validate compose file syntax
        success, output = self.run_command(
            f"docker-compose -f {self.compose_file} config", "Compose file validation"
        )

        if not success:
            self.log("Docker Compose file validation failed", "error")
            return False

        # Parse services from compose file
        with open(self.compose_file, "r") as f:
            compose_config = yaml.safe_load(f)

        if "services" in compose_config:
            self.containers = list(compose_config["services"].keys())
            self.log(f"Found services: {', '.join(self.containers)}", "info")
        else:
            self.log("No services defined in compose file", "warning")

        return True

    def validate_dockerfiles(self) -> bool:
        """Validate all Dockerfiles exist and are valid."""
        self.log("Validating Dockerfiles...")

        dockerfiles = [
            ("Dockerfile", "Backend Dockerfile"),
            ("frontend/Dockerfile", "Frontend Dockerfile"),
        ]

        all_valid = True
        for dockerfile_path, description in dockerfiles:
            if Path(dockerfile_path).exists():
                # Validate Dockerfile syntax using hadolint if available
                success, output = self.run_command(
                    f"docker run --rm -i hadolint/hadolint < {dockerfile_path}",
                    f"Linting {description}",
                )
                if not success:
                    self.log(f"{description} has linting warnings", "warning")
                else:
                    self.log(f"{description} validated", "success")
            else:
                self.log(f"{description} not found at {dockerfile_path}", "warning")

        return all_valid

    def build_images(self) -> bool:
        """Build Docker images."""
        self.log("Building Docker images...")

        # Build with compose
        command = f"docker-compose -f {self.compose_file} build"
        if self.environment == "production":
            command += " --no-cache"  # Clean build for production

        success, output = self.run_command(command, "Building Docker images")

        if not success:
            self.log("Docker image build failed", "error")
            return False

        # List built images
        success, output = self.run_command(
            "docker images --format 'table {{.Repository}}:{{.Tag}}\t{{.Size}}' | grep ruleiq",
            "Listing built images",
        )

        return True

    def start_containers(self) -> bool:
        """Start Docker containers."""
        self.log("Starting Docker containers...")

        # Start containers in detached mode
        command = f"docker-compose -f {self.compose_file} up -d"
        success, output = self.run_command(command, "Starting containers")

        if not success:
            self.log("Failed to start containers", "error")
            return False

        # Wait for containers to be ready
        time.sleep(5)

        # Check container status
        return self.check_container_health()

    def check_container_health(self) -> bool:
        """Check health status of running containers."""
        self.log("Checking container health...")

        success, output = self.run_command(
            f"docker-compose -f {self.compose_file} ps", "Container status check"
        )

        if not success:
            return False

        # Check individual container health
        all_healthy = True
        for service in self.containers:
            success, output = self.run_command(
                f"docker-compose -f {self.compose_file} ps {service}", f"Checking {service}"
            )

            if not success or "Exit" in output:
                self.log(f"Service {service} is not healthy", "error")
                all_healthy = False

                # Get logs for debugging
                self.run_command(
                    f"docker-compose -f {self.compose_file} logs --tail=20 {service}",
                    f"Logs for {service}",
                )

        return all_healthy

    def run_health_checks(self) -> bool:
        """Run application health checks on containers."""
        self.log("Running application health checks...")

        health_checks = [
            ("http://localhost:8000/health", "Backend health check"),
            ("http://localhost:3000", "Frontend health check"),
            ("http://localhost:8000/api/v1/docs", "API documentation check"),
        ]

        all_healthy = True
        for url, description in health_checks:
            success, output = self.run_command(
                f"curl -f -s -o /dev/null -w '%{{http_code}}' {url}", description
            )

            if success and "200" in output:
                self.log(f"✅ {description} passed", "success")
            else:
                self.log(f"❌ {description} failed", "error")
                all_healthy = False

        return all_healthy

    def test_service_connectivity(self) -> bool:
        """Test connectivity between services."""
        self.log("Testing service connectivity...")

        # Test database connection from backend
        success, output = self.run_command(
            f"docker-compose -f {self.compose_file} exec -T backend python -c "
            '"from database.db_setup import engine; engine.connect()"',
            "Database connectivity from backend",
        )

        if not success:
            self.log("Database connectivity test failed", "error")
            return False

        # Test Redis connection if configured
        if "redis" in self.containers:
            success, output = self.run_command(
                f"docker-compose -f {self.compose_file} exec -T redis redis-cli ping",
                "Redis connectivity",
            )

            if not success:
                self.log("Redis connectivity test failed", "warning")

        return True

    def run_migrations(self) -> bool:
        """Run database migrations in container."""
        self.log("Running database migrations...")

        # Check if alembic is available
        success, output = self.run_command(
            f"docker-compose -f {self.compose_file} exec -T backend alembic current",
            "Checking migration status",
        )

        if success:
            # Run migrations
            success, output = self.run_command(
                f"docker-compose -f {self.compose_file} exec -T backend alembic upgrade head",
                "Running migrations",
            )

            if not success:
                self.log("Migration failed", "error")
                return False
        else:
            self.log("Alembic not configured, skipping migrations", "warning")

        return True

    def setup_volumes(self) -> bool:
        """Ensure persistent volumes are properly configured."""
        self.log("Setting up persistent volumes...")

        # Check volume configuration
        success, output = self.run_command(
            "docker volume ls --format 'table {{.Name}}\t{{.Driver}}'", "Listing Docker volumes"
        )

        # Create necessary volumes if not exist
        volumes = ["ruleiq_postgres_data", "ruleiq_redis_data"]
        for volume in volumes:
            success, output = self.run_command(
                f"docker volume create {volume}", f"Creating volume {volume}"
            )

        return True

    def cleanup_old_containers(self) -> bool:
        """Clean up old containers and images."""
        self.log("Cleaning up old containers and images...")

        # Stop old containers
        self.run_command(f"docker-compose -f {self.compose_file} down", "Stopping old containers")

        # Remove dangling images
        self.run_command("docker image prune -f", "Removing dangling images")

        # Remove unused volumes (careful with this)
        if self.environment != "production":
            self.run_command("docker volume prune -f", "Removing unused volumes")

        return True

    def deploy(self) -> bool:
        """Execute full Docker deployment.

        Returns:
            Boolean indicating deployment success
        """
        self.log("=" * 60)
        self.log(f"🐳 DOCKER DEPLOYMENT - Environment: {self.environment}", "docker")
        self.log("=" * 60)

        # Check Docker installation
        if not self.check_docker_installation():
            return False

        # Validate configuration
        if not self.validate_compose_file():
            return False

        # Validate Dockerfiles
        self.validate_dockerfiles()

        # Setup volumes
        if not self.setup_volumes():
            return False

        # Clean up old containers (optional)
        if self.environment != "production":
            self.cleanup_old_containers()

        # Build images
        if not self.build_images():
            return False

        # Start containers
        if not self.start_containers():
            return False

        # Run migrations
        if not self.run_migrations():
            self.log("Migration failed but continuing", "warning")

        # Test connectivity
        if not self.test_service_connectivity():
            self.log("Service connectivity issues detected", "warning")

        # Run health checks
        time.sleep(10)  # Wait for services to fully initialize
        if not self.run_health_checks():
            self.log("Health checks failed", "error")
            return False

        self.log("=" * 60)
        self.log("🎉 Docker deployment completed successfully!", "success")
        self.log("=" * 60)

        # Show running containers
        self.run_command(f"docker-compose -f {self.compose_file} ps", "Final container status")

        return True

    def stop(self) -> bool:
        """Stop all containers."""
        self.log("Stopping containers...")

        success, output = self.run_command(
            f"docker-compose -f {self.compose_file} stop", "Stopping containers"
        )

        return success

    def restart(self) -> bool:
        """Restart all containers."""
        self.log("Restarting containers...")

        success, output = self.run_command(
            f"docker-compose -f {self.compose_file} restart", "Restarting containers"
        )

        time.sleep(10)
        return self.check_container_health()

    def logs(self, service: Optional[str] = None, lines: int = 100):
        """Display container logs.

        Args:
            service: Specific service to show logs for
            lines: Number of lines to display
        """
        if service:
            command = f"docker-compose -f {self.compose_file} logs --tail={lines} {service}"
        else:
            command = f"docker-compose -f {self.compose_file} logs --tail={lines}"

        self.run_command(command, "Displaying logs")

    def exec_command(self, service: str, command: str) -> Tuple[bool, str]:
        """Execute command in a running container.

        Args:
            service: Service name
            command: Command to execute

        Returns:
            Tuple of (success, output)
        """
        full_command = f"docker-compose -f {self.compose_file} exec -T {service} {command}"
        return self.run_command(full_command, f"Executing in {service}")

    def scale(self, service: str, replicas: int) -> bool:
        """Scale a service to specified number of replicas.

        Args:
            service: Service name
            replicas: Number of replicas

        Returns:
            Boolean indicating success
        """
        self.log(f"Scaling {service} to {replicas} replicas...")

        success, output = self.run_command(
            f"docker-compose -f {self.compose_file} up -d --scale {service}={replicas}",
            f"Scaling {service}",
        )

        return success


def main():
    """Main entry point for Docker manager."""
    parser = argparse.ArgumentParser(description="Docker deployment manager for ruleIQ")
    parser.add_argument(
        "--action",
        choices=["deploy", "stop", "restart", "logs", "status", "clean"],
        default="deploy",
        help="Action to perform",
    )
    parser.add_argument(
        "--env",
        choices=["staging", "production", "test"],
        default="staging",
        help="Target environment",
    )
    parser.add_argument("--compose-file", help="Path to Docker Compose file")
    parser.add_argument("--service", help="Specific service for actions")
    parser.add_argument("--scale", type=int, help="Number of replicas for scaling")

    args = parser.parse_args()

    # Create Docker manager
    manager = DockerManager(environment=args.env, compose_file=args.compose_file)

    # Execute action
    if args.action == "deploy":
        success = manager.deploy()
    elif args.action == "stop":
        success = manager.stop()
    elif args.action == "restart":
        success = manager.restart()
    elif args.action == "logs":
        manager.logs(service=args.service)
        success = True
    elif args.action == "status":
        success = manager.check_container_health()
    elif args.action == "clean":
        success = manager.cleanup_old_containers()
    else:
        success = False

    # Handle scaling if requested
    if args.scale and args.service:
        success = manager.scale(args.service, args.scale)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
