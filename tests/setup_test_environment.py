#!/usr/bin/env python3
"""
Test Environment Setup Script for ruleIQ
Configures databases, services, and environment for testing
"""

import os
import sys
import subprocess
import time
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import redis
from pathlib import Path


class TestEnvironmentSetup:
    """Manages test environment setup and teardown"""

    def __init__(self):
        self.test_db_name = "compliance_test"
        self.test_db_port = 5433
        self.test_db_user = "postgres"
        self.test_db_password = "postgres"
        self.test_redis_port = 6380  # Different port for test Redis
        self.project_root = Path(__file__).parent.parent

    def check_postgresql_running(self, port=5432):
        """Check if PostgreSQL is running on specified port"""
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=port,
                user=self.test_db_user,
                password=self.test_db_password,
                database="postgres",
            )
            conn.close()
            return True
        except Exception:
            return False

    def setup_test_database(self):
        """Create and configure test database"""
        print(f"🔧 Setting up test database '{self.test_db_name}' on port {self.test_db_port}...")

        # Check if we need to use Docker for PostgreSQL
        if not self.check_postgresql_running(self.test_db_port):
            print(
                f"📦 PostgreSQL not running on port {self.test_db_port}, starting Docker container..."
            )
            self.start_postgres_docker()
            time.sleep(5)  # Wait for container to be ready

        # Connect to PostgreSQL
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=self.test_db_port,
                user=self.test_db_user,
                password=self.test_db_password,
                database="postgres",
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # Check if database exists
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (self.test_db_name,),
            )
            exists = cursor.fetchone()

            if exists:
                print(f"✅ Test database '{self.test_db_name}' already exists")
            else:
                cursor.execute(f"CREATE DATABASE {self.test_db_name}")
                print(f"✅ Created test database '{self.test_db_name}'")

            cursor.close()
            conn.close()

            # Apply migrations
            self.apply_migrations()

        except (Exception, ValueError) as e:
            print(f"❌ Error setting up database: {e}")
            sys.exit(1)

    def start_postgres_docker(self):
        """Start PostgreSQL in Docker container for testing"""
        container_name = "ruleiq-test-postgres"

        # Check if container exists
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )

        if container_name in result.stdout:
            # Start existing container
            subprocess.run(["docker", "start", container_name])
            print(f"✅ Started existing container '{container_name}'")
        else:
            # Create new container
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    container_name,
                    "-e",
                    f"POSTGRES_PASSWORD={self.test_db_password}",
                    "-e",
                    f"POSTGRES_USER={self.test_db_user}",
                    "-p",
                    f"{self.test_db_port}:5432",
                    "postgres:15-alpine",
                ]
            )
            print(f"✅ Created and started new container '{container_name}'")

    def setup_test_redis(self):
        """Setup Redis for test caching"""
        print(f"🔧 Setting up test Redis on port {self.test_redis_port}...")

        try:
            # Check if Redis is already running
            r = redis.Redis(host="localhost", port=self.test_redis_port, db=0)
            r.ping()
            print(f"✅ Redis already running on port {self.test_redis_port}")
        except ValueError:
            print(f"📦 Starting Redis Docker container on port {self.test_redis_port}...")
            self.start_redis_docker()

    def start_redis_docker(self):
        """Start Redis in Docker container for testing"""
        container_name = "ruleiq-test-redis"

        # Check if container exists
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )

        if container_name in result.stdout:
            subprocess.run(["docker", "start", container_name])
            print(f"✅ Started existing container '{container_name}'")
        else:
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    container_name,
                    "-p",
                    f"{self.test_redis_port}:6379",
                    "redis:7-alpine",
                ]
            )
            print(f"✅ Created and started new container '{container_name}'")

    def apply_migrations(self):
        """Apply database migrations using Alembic"""
        print("🔄 Applying database migrations...")

        # Set test database URL
        os.environ["DATABASE_URL"] = (
            f"postgresql://{self.test_db_user}:{self.test_db_password}@"
            f"localhost:{self.test_db_port}/{self.test_db_name}",
        )

        try:
            # Run Alembic migrations
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                print("✅ Migrations applied successfully")
            else:
                print(f"⚠️ Migration output: {result.stdout}")
                if result.stderr:
                    print(f"⚠️ Migration errors: {result.stderr}")
        except FileNotFoundError:
            print("⚠️ Alembic not found, skipping migrations")

    def create_env_file(self):
        """Create .env.test file with test configuration"""
        print("📝 Creating .env.test configuration file...")

        env_content = f"""# Test Environment Configuration
# Auto-generated by setup_test_environment.py

# Database Configuration
DATABASE_URL=postgresql://{self.test_db_user}:{self.test_db_password}@localhost:{self.test_db_port}/{self.test_db_name}
TEST_DATABASE_URL=postgresql://{self.test_db_user}:{self.test_db_password}@localhost:{self.test_db_port}/{self.test_db_name}
ASYNC_DATABASE_URL=postgresql+asyncpg://{self.test_db_user}:{self.test_db_password}@localhost:{self.test_db_port}/{self.test_db_name}

# Redis Configuration
REDIS_URL=redis://localhost:{self.test_redis_port}/0
REDIS_HOST=localhost
REDIS_PORT={self.test_redis_port}
REDIS_DB=0

# Environment
ENVIRONMENT=testing
DEBUG=True

# API Keys (use test/mock values)
JWT_SECRET_KEY=test-secret-key-for-testing-only
OPENAI_API_KEY=sk-test-key
ANTHROPIC_API_KEY=test-key
GOOGLE_API_KEY=test-key

# Feature Flags
ENABLE_CACHE=False
ENABLE_MONITORING=False
ENABLE_RATE_LIMITING=False

# Service URLs (mock/test endpoints)
SUPABASE_URL=http://localhost:8000/mock-supabase
SUPABASE_SERVICE_KEY=test-service-key
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=test-password
"""

        env_file_path = self.project_root / ".env.test"
        with open(env_file_path, "w") as f:
            f.write(env_content)

        print(f"✅ Created {env_file_path}")

    def run_tests_with_coverage(self):
        """Run tests with coverage reporting"""
        print("\n🧪 Running tests with coverage...")

        # Set environment variables
        os.environ["ENVIRONMENT"] = "testing"
        os.environ["DATABASE_URL"] = (
            f"postgresql://{self.test_db_user}:{self.test_db_password}@"
            f"localhost:{self.test_db_port}/{self.test_db_name}",
        )
        os.environ["REDIS_URL"] = f"redis://localhost:{self.test_redis_port}/0"

        # Run pytest with coverage
        result = subprocess.run(
            [
                "pytest",
                "--cov=api",
                "--cov=services",
                "--cov=database",
                "--cov=utils",
                "--cov=core",
                "--cov=config",
                "--cov-report=xml",
                "--cov-report=html",
                "--cov-report=term-missing",
                "--tb=short",
                "-v",
                "tests/unit",  # Start with unit tests
                "--maxfail=5",
            ],
            cwd=self.project_root,
        )

        if result.returncode == 0:
            print("✅ Tests passed with coverage generated")
        else:
            print("⚠️ Some tests failed, but coverage was generated")

        return result.returncode

    def cleanup(self):
        """Clean up test environment"""
        print("\n🧹 Cleaning up test environment...")

        # Stop Docker containers if needed
        subprocess.run(["docker", "stop", "ruleiq-test-postgres"], capture_output=True)
        subprocess.run(["docker", "stop", "ruleiq-test-redis"], capture_output=True)

        print("✅ Cleanup complete")

    def setup(self):
        """Run complete test environment setup"""
        print("=" * 60)
        print("🚀 ruleIQ Test Environment Setup")
        print("=" * 60)

        try:
            # Setup components
            self.setup_test_database()
            self.setup_test_redis()
            self.create_env_file()

            print("\n" + "=" * 60)
            print("✅ Test environment setup complete!")
            print("=" * 60)

            print("\n📋 Configuration Summary:")
            print(f"  • Database: {self.test_db_name} on port {self.test_db_port}")
            print(f"  • Redis: port {self.test_redis_port}")
            print("  • Config file: .env.test")
            print("\n🏃 To run tests with coverage:")
            print("  python tests/setup_test_environment.py --run-tests")

        except (OSError, Exception, ValueError) as e:
            print(f"\n❌ Setup failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    setup = TestEnvironmentSetup()

    if "--cleanup" in sys.argv:
        setup.cleanup()
    elif "--run-tests" in sys.argv:
        setup.setup()
        exit_code = setup.run_tests_with_coverage()
        sys.exit(exit_code)
    else:
        setup.setup()
