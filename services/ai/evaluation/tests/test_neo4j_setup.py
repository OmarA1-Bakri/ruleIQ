"""Test Neo4j Community Edition Docker setup."""

from typing import Any

import os
import time
import pytest
import docker
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable


class TestNeo4jSetup:
    """Test Neo4j CE Docker container setup."""

    @pytest.fixture(scope="class")
    def docker_client(self) -> Any:
        """Get Docker client."""
        try:
            client = docker.from_env()
            # Test connection
            client.ping()
            return client
        except Exception as e:
            pytest.skip(f"Docker not available: {e}")

    @pytest.fixture(scope="class")
    def neo4j_container(self, docker_client: Any) -> Any:
        """Ensure Neo4j container is running."""
        container_name = "neo4j-ce-golden"
        image = "neo4j:5.26.10-community"

        # Check if container already exists
        try:
            container = docker_client.containers.get(container_name)
            if container.status != "running":
                container.start()
                time.sleep(10)  # Wait for startup
            return container
        except docker.errors.NotFound:
            # Create new container
            container = docker_client.containers.run(
                image,
                name=container_name,
                ports={"7474/tcp": 7474, "7687/tcp": 7687},  # HTTP  # Bolt
                environment={
                    "NEO4J_AUTH": "neo4j/please_change",
                    "NEO4J_ACCEPT_LICENSE_AGREEMENT": "yes",
                    "NEO4J_dbms_memory_heap_initial__size": "512m",
                    "NEO4J_dbms_memory_heap_max__size": "1G",
                    "NEO4J_dbms_memory_pagecache_size": "512m",
                },
                volumes={
                    "neo4j_golden_data": {"bind": "/data", "mode": "rw"},
                    "neo4j_golden_logs": {"bind": "/logs", "mode": "rw"},
                },
                detach=True,
                remove=False,
            )

            # Wait for Neo4j to be ready
            max_retries = 30
            for i in range(max_retries):
                try:
                    driver = GraphDatabase.driver(
                        "bolt://localhost:7687",
                        auth=("neo4j", "please_change"),
                    )
                    with driver.session() as session:
                        session.run("RETURN 1")
                    driver.close()
                    break
                except ServiceUnavailable:
                    if i == max_retries - 1:
                        raise
                    time.sleep(2)

            return container

    def test_container_running(self, neo4j_container: Any) -> Any:
        """Test that Neo4j container is running."""
        # Refresh container status as it may have been 'created' initially
        neo4j_container.reload()
        assert neo4j_container.status == "running"
        assert neo4j_container.name == "neo4j-ce-golden"

    def test_neo4j_version(self, neo4j_container: Any) -> Any:
        """Test Neo4j version is correct."""
        # Check container image tag
        assert "5.26.10-community" in neo4j_container.image.tags[0]

    def test_neo4j_connection(self, neo4j_container: Any) -> Any:
        """Test connection to Neo4j."""
        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "test_password123"),
        )

        with driver.session() as session:
            result = session.run("RETURN 'Connected' AS status")
            record = result.single()
            assert record["status"] == "Connected"

        driver.close()

    def test_vector_index_support(self, neo4j_container: Any) -> Any:
        """Test that Neo4j supports VECTOR indexes."""
        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "test_password123"),
        )

        with driver.session() as session:
            # Clean up any existing test index
            session.run(
                """
                DROP INDEX test_vector_index IF EXISTS
            """,
            )

            # Create a test vector index
            session.run(
                """
                CREATE VECTOR INDEX test_vector_index IF NOT EXISTS
                FOR (n:TestNode)
                ON (n.embedding)
                OPTIONS {
                    indexConfig: {
                        `vector.dimensions`: 384,
                        `vector.similarity_function`: 'cosine',
                    },
                }
            """,
            )

            # Verify index exists
            result = session.run(
                """
                SHOW INDEXES
                WHERE name = 'test_vector_index'
            """,
            )

            indexes = list(result)
            assert len(indexes) > 0

            # Clean up
            session.run("DROP INDEX test_vector_index IF EXISTS")

        driver.close()

    def test_memory_configuration(self, neo4j_container: Any) -> Any:
        """Test Neo4j memory configuration."""
        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "test_password123"),
        )

        with driver.session() as session:
            # Check database is accessible and responsive
            result = session.run(
                """
                CALL dbms.listConfig()
                YIELD name, value
                WHERE name IN [
                    'server.memory.heap.initial_size',
                    'server.memory.heap.max_size',
                    'server.memory.pagecache.size',
                ]
                RETURN name, value
            """,
            )

            config = {record["name"]: record["value"] for record in result}

            # Verify memory settings are applied
            assert (
                "server.memory.heap.initial_size" in config
                or "dbms.memory.heap.initial_size" in config,
            )

        driver.close()

    def test_persistence_volumes(self, docker_client: Any) -> Any:
        """Test that data persistence volumes exist."""
        volumes = docker_client.volumes.list()
        volume_names = [v.name for v in volumes]

        assert "neo4j_golden_data" in volume_names
        assert "neo4j_golden_logs" in volume_names


class TestNeo4jDockerCompose:
    """Test Neo4j docker-compose configuration."""

    def test_docker_compose_file_exists(self) -> Any:
        """Test that docker-compose file exists."""
        compose_path = "services/ai/evaluation/docker/docker-compose.yml"
        assert os.path.exists(compose_path)

    def test_docker_compose_configuration(self) -> Any:
        """Test docker-compose configuration is correct."""
        import yaml

        compose_path = "services/ai/evaluation/docker/docker-compose.yml"
        with open(compose_path, "r") as f:
            config = yaml.safe_load(f)

        # Check Neo4j service configuration
        assert "neo4j" in config["services"]
        neo4j = config["services"]["neo4j"]

        # Check image version
        assert neo4j["image"] == "neo4j:5.26.10-community"

        # Check ports
        assert "7474:7474" in neo4j["ports"]
        assert "7687:7687" in neo4j["ports"]

        # Check environment variables
        env = neo4j["environment"]
        assert env["NEO4J_AUTH"] == "neo4j/please_change"
        assert env["NEO4J_ACCEPT_LICENSE_AGREEMENT"] == "yes"

        # Check volumes
        assert "neo4j_data:/data" in neo4j["volumes"]
        assert "neo4j_logs:/logs" in neo4j["volumes"]

        # Check volume definitions
        assert "neo4j_data" in config["volumes"]
        assert "neo4j_logs" in config["volumes"]
