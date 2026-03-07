"""Test Neo4j connection and setup module."""

from typing import Any
from unittest.mock import Mock, patch
from neo4j.exceptions import ServiceUnavailable

# Import the module we'll create
from services.ai.evaluation.infrastructure.neo4j_setup import (
    Neo4jConnection,
    setup_neo4j_container,
    wait_for_neo4j,
    create_vector_indexes,
    get_neo4j_driver,
)


class TestNeo4jConnection:
    """Test Neo4j connection wrapper."""

    def test_connection_singleton(self) -> Any:
        """Test Neo4j connection is a singleton."""
        conn1 = Neo4jConnection()
        conn2 = Neo4jConnection()
        assert conn1 is conn2

    @patch("services.ai.evaluation.infrastructure.neo4j_setup.GraphDatabase")
    def test_get_driver_creates_driver(self, mock_graph_db: Any) -> Any:
        """Test get_driver creates driver if none exists."""
        mock_driver = Mock()
        mock_graph_db.driver.return_value = mock_driver

        conn = Neo4jConnection()
        conn._driver = None  # Reset driver

        driver = conn.get_driver()

        assert driver == mock_driver
        mock_graph_db.driver.assert_called_once_with(
            "bolt://localhost:7687",
            auth=("neo4j", "please_change"),
        )

    def test_get_driver_returns_existing(self) -> Any:
        """Test get_driver returns existing driver."""
        conn = Neo4jConnection()
        mock_driver = Mock()
        conn._driver = mock_driver

        driver = conn.get_driver()
        assert driver == mock_driver

    def test_close_driver(self) -> Any:
        """Test close_driver closes the driver."""
        conn = Neo4jConnection()
        mock_driver = Mock()
        conn._driver = mock_driver

        conn.close()

        mock_driver.close.assert_called_once()
        assert conn._driver is None

    def test_execute_query(self) -> Any:
        """Test execute_query runs cypher query."""
        conn = Neo4jConnection()
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()

        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        mock_session.run.return_value = mock_result

        conn._driver = mock_driver

        result = conn.execute_query("RETURN 1 AS num")

        assert result == mock_result
        mock_session.run.assert_called_once_with("RETURN 1 AS num", None)

    def test_execute_query_with_params(self) -> Any:
        """Test execute_query with parameters."""
        conn = Neo4jConnection()
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()

        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        mock_session.run.return_value = mock_result

        conn._driver = mock_driver

        params = {"name": "test"}
        result = conn.execute_query("MATCH (n {name: $name}) RETURN n", params)

        assert result == mock_result
        mock_session.run.assert_called_once_with(
            "MATCH (n {name: $name}) RETURN n",
            params,
        )


class TestNeo4jSetupFunctions:
    """Test Neo4j setup helper functions."""

    @patch("services.ai.evaluation.infrastructure.neo4j_setup.docker")
    def test_setup_neo4j_container_existing(self, mock_docker: Any) -> Any:
        """Test setup with existing container."""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.status = "running"

        mock_docker.from_env.return_value = mock_client
        mock_client.containers.get.return_value = mock_container

        container = setup_neo4j_container()

        assert container == mock_container
        mock_client.containers.get.assert_called_once_with("neo4j-ce-golden")

    @patch("services.ai.evaluation.infrastructure.neo4j_setup.docker")
    @patch("services.ai.evaluation.infrastructure.neo4j_setup.wait_for_neo4j")
    def test_setup_neo4j_container_create_new(self, mock_wait: Any, mock_docker: Any) -> Any:
        """Test setup creates new container if not exists."""
        mock_client = Mock()
        mock_container = Mock()

        mock_docker.from_env.return_value = mock_client
        mock_docker.errors.NotFound = Exception
        mock_client.containers.get.side_effect = Exception("Not found")
        mock_client.containers.run.return_value = mock_container

        container = setup_neo4j_container()

        assert container == mock_container
        mock_client.containers.run.assert_called_once()
        mock_wait.assert_called_once()

    @patch("services.ai.evaluation.infrastructure.neo4j_setup.GraphDatabase")
    @patch("services.ai.evaluation.infrastructure.neo4j_setup.time")
    def test_wait_for_neo4j_success(self, mock_time: Any, mock_graph_db: Any) -> Any:
        """Test wait_for_neo4j succeeds when Neo4j is ready."""
        mock_driver = Mock()
        mock_session = Mock()

        mock_graph_db.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)

        result = wait_for_neo4j(max_retries=1)

        assert result is True
        mock_session.run.assert_called_once_with("RETURN 1")

    @patch("services.ai.evaluation.infrastructure.neo4j_setup.GraphDatabase")
    @patch("services.ai.evaluation.infrastructure.neo4j_setup.time")
    def test_wait_for_neo4j_timeout(self, mock_time: Any, mock_graph_db: Any) -> Any:
        """Test wait_for_neo4j times out."""
        mock_graph_db.driver.side_effect = ServiceUnavailable("Not ready")

        result = wait_for_neo4j(max_retries=1)

        assert result is False

    def test_create_vector_indexes(self) -> Any:
        """Test vector index creation."""
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.single.return_value = None
        mock_conn.execute_query.return_value = mock_result

        create_vector_indexes(mock_conn)

        # Should create document and chunk indexes
        assert mock_conn.execute_query.call_count >= 2

        # Check that vector indexes are created
        calls = mock_conn.execute_query.call_args_list
        index_queries = [call[0][0] for call in calls]

        # Should have queries for document and chunk indexes
        assert any("document_embedding_index" in q for q in index_queries)
        assert any("chunk_embedding_index" in q for q in index_queries)

    @patch("services.ai.evaluation.infrastructure.neo4j_setup.Neo4jConnection")
    def test_get_neo4j_driver(self, mock_conn_class: Any) -> Any:
        """Test get_neo4j_driver returns driver."""
        mock_conn = Mock()
        mock_driver = Mock()
        mock_conn.get_driver.return_value = mock_driver
        mock_conn_class.return_value = mock_conn

        driver = get_neo4j_driver()

        assert driver == mock_driver
        mock_conn.get_driver.assert_called_once()
