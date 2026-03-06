#!/usr/bin/env python3
"""Test LangGraph instantiation and basic functionality."""

import asyncio
import os
from uuid import uuid4
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO)


async def test_instantiation():
    """Test basic instantiation of MasterIntegrationGraph."""

    print("🔧 Testing MasterIntegrationGraph instantiation...")

    # Import the graph
    from langgraph_agent.graph.master_integration_graph import MasterIntegrationGraph

    print("✅ Import successful")

    # Check for database URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("⚠️  No DATABASE_URL found, using test configuration")
        db_url = "postgresql://test:test@localhost:5432/testdb"

    try:
        # Create instance
        print("📊 Creating MasterIntegrationGraph instance...")
        graph = await MasterIntegrationGraph.create(
            database_url=db_url,
            enable_streaming=True,
        )
        print("✅ Graph instance created successfully")

        # Test state creation
        print("📝 Testing state creation...")
        from langgraph_agent.graph.enhanced_state import create_enhanced_initial_state

        state = create_enhanced_initial_state(
            session_id="test-session",
            company_id=uuid4(),
            initial_message="Test compliance query",
        )
        print(f"✅ State created with session: {state['session_id']}")

        # Test graph structure
        print("🔍 Checking graph structure...")
        if hasattr(graph, "graph") and graph.graph:
            print(
                f"✅ Graph has {len(graph.graph.nodes) if hasattr(graph.graph, 'nodes') else 'unknown number of'} nodes",
            )

        if hasattr(graph, "checkpointer"):
            print("✅ Checkpointer configured")

        if hasattr(graph, "rag_system"):
            print("✅ RAG system initialized")

        if hasattr(graph, "error_handler"):
            print("✅ Error handler configured")

        print("\n🎉 All basic tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_instantiation())
    sys.exit(0 if success else 1)
