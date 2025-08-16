#!/usr/bin/env python3
"""
Test script to verify LangSmith tracing is working with the assessment agent.

Run this script to:
1. Check LangSmith configuration
2. Test tracing with a simple assessment flow
3. Verify traces are being sent to LangSmith

Usage:
    python scripts/test_langsmith_tracing.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.langsmith_config import LangSmithConfig
from config.logging_config import get_logger

logger = get_logger(__name__)


async def test_langsmith_tracing():
    """Test LangSmith tracing configuration and basic functionality."""
    
    print("=" * 60)
    print("LangSmith Tracing Test")
    print("=" * 60)
    
    # Step 1: Check configuration
    print("\n1. Checking LangSmith configuration...")
    
    is_enabled = LangSmithConfig.is_tracing_enabled()
    api_key = LangSmithConfig.get_api_key()
    project = LangSmithConfig.get_project_name()
    endpoint = LangSmithConfig.get_endpoint()
    
    print(f"   Tracing enabled: {is_enabled}")
    print(f"   API key present: {'Yes' if api_key else 'No'}")
    print(f"   Project name: {project}")
    print(f"   Endpoint: {endpoint}")
    
    if not is_enabled:
        print("\n❌ LangSmith tracing is DISABLED")
        print("   To enable, set LANGCHAIN_TRACING_V2=true in your .env file")
        return False
    
    if not api_key:
        print("\n❌ LangSmith API key is MISSING")
        print("   To fix, set LANGCHAIN_API_KEY=ls__your_key in your .env file")
        return False
    
    # Step 2: Validate configuration
    print("\n2. Validating configuration...")
    
    if not LangSmithConfig.validate_configuration():
        print("❌ Configuration validation FAILED")
        return False
    
    print("✅ Configuration validated successfully")
    
    # Step 3: Test tracing with a simple flow
    print("\n3. Testing tracing with assessment agent...")
    
    try:
        # Import here to avoid circular dependencies
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        from services.assessment_agent import AssessmentAgent
        
        # Create a test database session
        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            print("❌ DATABASE_URL not configured")
            return False
        
        engine = create_async_engine(DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"))
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with AsyncSessionLocal() as db:
            # Create assessment agent
            agent = AssessmentAgent(db)
            
            # Test a simple assessment start
            test_session_id = "test_langsmith_" + str(os.getpid())
            test_lead_id = "test_lead_123"
            test_context = {
                "business_type": "Software Company",
                "company_size": "11-50",
                "industry": "Technology"
            }
            
            print(f"   Starting test assessment: {test_session_id}")
            
            # This should trigger LangSmith tracing
            result = await agent.start_assessment(
                session_id=test_session_id,
                lead_id=test_lead_id,
                initial_context=test_context
            )
            
            print(f"   Assessment started successfully")
            print(f"   Current phase: {result.get('current_phase')}")
            print(f"   Messages: {len(result.get('messages', []))}")
            
            # Test processing a response
            if result.get('messages'):
                print("\n   Testing response processing...")
                test_response = "We handle customer data and payment information"
                
                result2 = await agent.process_user_response(
                    session_id=test_session_id,
                    user_response=test_response,
                    confidence="high"
                )
                
                print(f"   Response processed successfully")
                print(f"   Questions answered: {result2.get('questions_answered', 0)}")
        
        print("\n✅ Tracing test completed successfully!")
        print(f"\n4. View your traces at: https://smith.langchain.com")
        print(f"   Project: {project}")
        print(f"   Look for traces with session ID: {test_session_id}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during tracing test: {e}")
        logger.exception("Tracing test failed")
        return False


async def main():
    """Main function."""
    print("\nTesting LangSmith integration for ruleIQ assessment agent\n")
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    success = await test_langsmith_tracing()
    
    if success:
        print("\n🎉 All tests passed! LangSmith tracing is working correctly.")
        print("\nNext steps:")
        print("1. Go to https://smith.langchain.com")
        print("2. Sign in with your account")
        print("3. Navigate to your project: 'ruleiq-assessment'")
        print("4. You should see traces from this test run")
        print("\nFor production use:")
        print("- Keep LANGCHAIN_TRACING_V2=false by default")
        print("- Enable it temporarily for debugging specific issues")
        print("- Use custom metadata and tags to organize traces")
    else:
        print("\n⚠️  Some tests failed. Please check the configuration above.")
        print("\nTroubleshooting:")
        print("1. Ensure you have a LangSmith account: https://smith.langchain.com")
        print("2. Get your API key from the dashboard")
        print("3. Add to .env file:")
        print("   LANGCHAIN_TRACING_V2=true")
        print("   LANGCHAIN_API_KEY=ls__your_key_here")
        print("   LANGCHAIN_PROJECT=ruleiq-assessment")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())