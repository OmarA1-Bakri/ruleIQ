"""
Test script for Agentic RAG integration
Quick verification that the system is working
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.agentic_integration import get_agentic_service


async def test_agentic_rag():
    """Test the agentic RAG system"""
    print("🚀 Testing Agentic RAG Integration")
    print("=" * 50)

    try:
        # Get the service
        service = get_agentic_service()

        # Initialize (this will process docs if needed)
        print("📚 Initializing service and processing documentation...")
        await service.initialize()

        # Get system status
        print("\n📊 Getting system status...")
        status = await service.get_system_status()
        print(f"Status: {status['status']}")
        print(f"Total chunks: {status['rag_system']['total_chunks']}")
        print(f"Total code examples: {status['rag_system']['total_code_examples']}")
        print(f"Available sources: {status['rag_system']['available_sources']}")

        # Test documentation query
        print("\n🔍 Testing documentation query...")
        doc_result = await service.query_documentation(
            query="How do I create a state graph in LangGraph?",
            source_filter="langgraph",
            query_type="documentation",
        )
        print(f"Answer: {doc_result['answer'][:200]}...")
        print(f"Confidence: {doc_result['confidence']}")
        print(f"Sources: {len(doc_result['sources'])}")

        # Test code examples
        print("\n💻 Testing code examples search...")
        code_result = await service.find_code_examples(
            task_description="state management with checkpointing",
            framework="langgraph",
        )
        print(f"Found {len(code_result['examples'])} examples")
        print(f"Explanation: {code_result['explanation'][:200]}...")

        # Test compliance agent
        print("\n🤖 Testing compliance agent...")
        compliance_result = await service.process_compliance_request(
            request="What are the key GDPR requirements for data processing?",
            user_id="test_user",
            trust_level=1,
        )
        print(f"Recommendation: {compliance_result.recommendation[:200]}...")
        print(f"Risk level: {compliance_result.risk_level}")
        print(f"Confidence: {compliance_result.confidence}")
        print(f"Requires approval: {compliance_result.requires_human_approval}")

        # Test implementation guidance
        print("\n📖 Testing implementation guidance...")
        guidance = await service.get_implementation_guidance(
            topic="agent design patterns",
            framework="pydantic_ai",
        )
        print(f"Guidance: {guidance[:200]}...")

        print("\n✅ All tests completed successfully!")
        print("🎉 Agentic RAG integration is working correctly!")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Set environment variables for testing
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/compliancegpt",
    )
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
    os.environ.setdefault("OPENAI_API_KEY", "your-openai-key-here")

    # Run the test
    asyncio.run(test_agentic_rag())
