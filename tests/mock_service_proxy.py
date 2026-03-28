"""
Mock Service Proxy - Intercepts and redirects service connections to test instances.
This allows existing tests to work without modification.
"""

import logging

logger = logging.getLogger(__name__)
import os
import sys
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
try:
    import psycopg2
except ImportError:  # pragma: no cover - optional in minimal test env
    psycopg2 = None

try:
    import psycopg
except ImportError:  # pragma: no cover - optional in minimal test env
    psycopg = None

try:
    import redis
except ImportError:  # pragma: no cover - optional in minimal test env
    redis = None
from sqlalchemy import create_engine
from urllib.parse import urlparse, urlunparse


class ServiceProxy:
    """
    Intercepts service connections and redirects to test instances.
    """

    def __init__(self):
        self.test_config = {
            "postgres": {
                "host": "localhost",
                "port": int(os.getenv("PGPORT", "5433")),
                "database": os.getenv("PGDATABASE", "compliance_test"),
                "user": os.getenv("PGUSER", "postgres"),
                "password": os.getenv("PGPASSWORD", "postgres"),
            },
            "redis": {
                "host": "localhost",
                "port": int(os.getenv("REDIS_PORT", "6380")),
                "db": int(os.getenv("REDIS_DB", "0")),
            },
        }

    def get_test_postgres_url(self, original_url=None):
        """Convert any PostgreSQL URL to test database URL."""
        cfg = self.test_config["postgres"]
        return f"postgresql://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['database']}"

    def get_test_redis_url(self, original_url=None):
        """Convert any Redis URL to test Redis URL."""
        cfg = self.test_config["redis"]
        return f"redis://{cfg['host']}:{cfg['port']}/{cfg['db']}"

    def patch_postgres_connections(self):
        """Patch all PostgreSQL connection methods to use test database."""
        test_url = self.get_test_postgres_url()
        if psycopg2 is not None:
            original_psycopg2_connect = psycopg2.connect

            def psycopg2_connect_wrapper(*args, **kwargs):
                # Remove conflicting parameters
                if "dsn" in kwargs:
                    del kwargs["dsn"]
                if "database" in kwargs:
                    del kwargs["database"]
                # Set test database parameters using dbname (psycopg2 standard)
                kwargs.update(
                    {
                        "host": self.test_config["postgres"]["host"],
                        "port": self.test_config["postgres"]["port"],
                        "dbname": self.test_config["postgres"]["database"],
                        "user": self.test_config["postgres"]["user"],
                        "password": self.test_config["postgres"]["password"],
                    }
                )
                return original_psycopg2_connect(*args, **kwargs)

            psycopg2.connect = psycopg2_connect_wrapper

        if psycopg is not None:
            original_psycopg_connect = psycopg.connect

            def psycopg_connect_wrapper(*args, **kwargs):
                if args and isinstance(args[0], str):
                    args = (test_url,) + args[1:]
                else:
                    kwargs.pop("dsn", None)
                    kwargs.pop("database", None)
                    kwargs.update(
                        {
                            "host": self.test_config["postgres"]["host"],
                            "port": self.test_config["postgres"]["port"],
                            "dbname": self.test_config["postgres"]["database"],
                            "user": self.test_config["postgres"]["user"],
                            "password": self.test_config["postgres"]["password"],
                        }
                    )
                return original_psycopg_connect(*args, **kwargs)

            psycopg.connect = psycopg_connect_wrapper

        original_create_engine = create_engine

        def create_engine_wrapper(url, *args, **kwargs):
            if isinstance(url, str) and ("postgresql" in url or "postgres" in url):
                url = test_url
            return original_create_engine(url, *args, **kwargs)

        import sqlalchemy

        sqlalchemy.create_engine = create_engine_wrapper

    def patch_redis_connections(self):
        """Patch all Redis connection methods to use test Redis."""
        if redis is None:
            return

        cfg = self.test_config["redis"]
        original_redis_init = redis.Redis.__init__

        def redis_init_wrapper(self, *args, **kwargs):
            kwargs.update({"host": cfg["host"], "port": cfg["port"], "db": cfg["db"]})
            if "connection_pool" in kwargs:
                del kwargs["connection_pool"]
            return original_redis_init(self, *args, **kwargs)

        original_from_url = redis.from_url

        def from_url_wrapper(url, **kwargs):
            test_url = f"redis://{cfg['host']}:{cfg['port']}/{cfg['db']}"
            return original_from_url(test_url, **kwargs)

        redis.Redis.__init__ = redis_init_wrapper
        redis.from_url = from_url_wrapper

    def patch_opentelemetry(self):
        """Mock OpenTelemetry to prevent export timeouts."""
        try:
            from unittest.mock import MagicMock
            from opentelemetry.exporter.otlp.proto.grpc import metric_exporter

            mock_metric_instance = MagicMock()
            mock_metric_instance.export = MagicMock(return_value=True)
            mock_metric_instance.shutdown = MagicMock(return_value=None)
            metric_exporter.OTLPMetricExporter = MagicMock(return_value=mock_metric_instance)
        except ImportError:
            pass
        try:
            from unittest.mock import MagicMock
            from opentelemetry.exporter.otlp.proto.grpc import trace_exporter

            mock_trace_instance = MagicMock()
            mock_trace_instance.export = MagicMock(return_value=True)
            mock_trace_instance.shutdown = MagicMock(return_value=None)
            trace_exporter.OTLPSpanExporter = MagicMock(return_value=mock_trace_instance)
        except ImportError:
            pass

    def patch_environment_variables(self):
        """Patch environment variables to point to test services."""
        test_env = {
            "DATABASE_URL": self.get_test_postgres_url(),
            "POSTGRES_HOST": self.test_config["postgres"]["host"],
            "POSTGRES_PORT": str(self.test_config["postgres"]["port"]),
            "POSTGRES_DB": self.test_config["postgres"]["database"],
            "POSTGRES_USER": self.test_config["postgres"]["user"],
            "POSTGRES_PASSWORD": self.test_config["postgres"]["password"],
            "REDIS_URL": self.get_test_redis_url(),
            "REDIS_HOST": self.test_config["redis"]["host"],
            "REDIS_PORT": str(self.test_config["redis"]["port"]),
            "REDIS_DB": str(self.test_config["redis"]["db"]),
            "OPENTELEMETRY_ENABLED": "false",
            "NEO4J_ENABLED": "false",
            "DISABLE_EXTERNAL_SERVICES": "true",
        }
        for key, value in test_env.items():
            os.environ[key] = value

    def activate(self):
        """Activate all service proxies."""
        self.patch_environment_variables()
        self.patch_postgres_connections()
        self.patch_redis_connections()
        self.patch_opentelemetry()
        self._patch_database_module()
        self._patch_cache_module()

    def _patch_database_module(self):
        """Patch the database module to use test configuration."""
        try:
            import database

            database.DATABASE_URL = self.get_test_postgres_url()
            if hasattr(database, "get_db_url"):
                database.get_db_url = lambda: self.get_test_postgres_url()
            if hasattr(database, "engine"):
                from sqlalchemy import create_engine

                database.engine = create_engine(self.get_test_postgres_url())
        except ImportError:
            pass

    def _patch_cache_module(self):
        """Patch cache modules to use test Redis."""
        if redis is None:
            return

        try:
            import config.cache

            cfg = self.test_config["redis"]
            config.cache.REDIS_HOST = cfg["host"]
            config.cache.REDIS_PORT = cfg["port"]
            config.cache.REDIS_DB = cfg["db"]
            if hasattr(config.cache, "get_redis_client"):
                original_get_redis = config.cache.get_redis_client

                def get_redis_wrapper(*args, **kwargs):
                    client = redis.Redis(host=cfg["host"], port=cfg["port"], db=cfg["db"])
                    return client

                config.cache.get_redis_client = get_redis_wrapper
        except ImportError:
            pass


service_proxy = ServiceProxy()


def setup_test_services():
    """
    Setup function to be called at the start of test sessions.
    This activates all service proxies.
    """
    service_proxy.activate()
    logger.info(
        "✅ Test service proxy activated - redirecting all connections to test instances",
    )
    logger.info("  PostgreSQL: localhost:%s" % service_proxy.test_config["postgres"]["port"])
    logger.info("  Redis: localhost:%s" % service_proxy.test_config["redis"]["port"])
    logger.info("  OpenTelemetry: Mocked (no exports)")


@contextmanager
def test_service_context():
    """
    Context manager for test services.
    """
    service_proxy.activate()
    try:
        yield service_proxy
    finally:
        pass
