"""
Test the updated hybrid agent with refactored architecture.
"""

import asyncio
from services.iq_agent_hybrid import HybridIQAgent, QueryType
from services.neo4j_service import Neo4jGraphRAGService
from unittest.mock import MagicMock, AsyncMock


async def test_hybrid_agent():
    """Test the updated hybrid agent."""
    print("Testing updated Hybrid IQ Agent with refactored architecture...")
    
    # Mock Neo4j service
    neo4j = MagicMock(spec=Neo4jGraphRAGService)
    neo4j.execute_query = AsyncMock(return_value={"data": []})
    
    # Mock postgres session
    postgres = MagicMock()
    
    # Create agent
    agent = HybridIQAgent(neo4j, postgres)
    
    # Test query classification
    print("\n1. Testing query classification:")
    test_queries = [
        "Conduct a compliance assessment",
        "Do we have privacy policy?",
        "What are the risks?",
        "How to implement GDPR?"
    ]
    
    for query in test_queries:
        query_type = agent._classify_query(query)
        print(f"   '{query[:30]}...' -> {query_type.value}")
    
    # Test quick answer (no DB required)
    print("\n2. Testing quick answer:")
    result = await agent._process_quick_answer("What is GDPR?")
    print(f"   Status: {result['status']}")
    print(f"   Method: {result['reasoning_method']}")
    
    # Test that repository integration is proper
    print("\n3. Checking repository integration:")
    print(f"   Compliance repo: {agent.compliance_repo is not None}")
    print(f"   Business repo: {agent.business_repo is not None}")
    print(f"   Evidence repo: {agent.evidence_repo is not None}")
    print(f"   Query classifier: {agent.query_classifier is not None}")
    print(f"   React agent: {agent.react_agent is not None}")
    
    print("\n✅ Hybrid agent integration test completed!")
    return True


if __name__ == "__main__":
    asyncio.run(test_hybrid_agent())