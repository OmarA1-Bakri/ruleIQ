#!/usr/bin/env python3
"""
Test AI functionality with Neon database
"""

import asyncio
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

# Import after loading env vars
from services.ai.assistant import ComplianceAssistant
from services.ai.safety_manager import AdvancedSafetyManager
from database.db_setup import init_db, get_async_db


async def test_ai_functionality():
    """Test core AI functionality"""
    print("🧪 Testing AI functionality with Neon database\n")

    # 1. Test database connection
    print("1️⃣ Testing Neon database connection...")
    try:
        init_db()
        print("✅ Database connection successful\n")
    except Exception as e:
        print(f"❌ Database connection failed: {e}\n")
        return

    # Run all tests within a database session
    async for db in get_async_db():
        # 2. Test AI Assistant initialization
        print("2️⃣ Testing AI Assistant initialization...")
        try:
            assistant = ComplianceAssistant(db)
            print("✅ AI Assistant initialized successfully\n")
        except Exception as e:
            print(f"❌ AI Assistant initialization failed: {e}\n")
            return

        # 3. Test Safety Manager
        print("3️⃣ Testing Safety Manager...")
        try:
            safety_manager = AdvancedSafetyManager()
            test_content = "Tell me about GDPR compliance requirements"
            safety_result = await safety_manager.check_safety(test_content)
            print(f"✅ Safety check passed: {safety_result.is_safe}")
            print(f"   Risk level: {safety_result.risk_level}\n")
        except Exception as e:
            print(f"❌ Safety Manager test failed: {e}\n")

        # 4. Test AI response generation
        print("4️⃣ Testing AI response generation...")
        try:
            # Create a simple test context
            test_question = "What are the key requirements for GDPR compliance?"

            # Test the assistant's response
            response = await assistant.get_assessment_help(
                question_text=test_question,
                question_type="regulatory_compliance",
                user_context={"industry": "technology", "size": "small"},
            )

            print("✅ AI Response generated successfully:")
            print(f"   Response type: {type(response)}")
            if hasattr(response, "guidance"):
                print(f"   Guidance preview: {response.guidance[:100]}...")
            print(
                f"   Has citations: {'citations' in response.__dict__ if hasattr(response, '__dict__') else 'N/A'}\n",
            )
        except Exception as e:
            print(f"❌ AI response generation failed: {e}\n")

        # 5. Test AI caching
        print("5️⃣ Testing AI response caching...")
        try:
            # Make the same request again to test caching
            start_time = time.time()
            cached_response = await assistant.get_assessment_help(
                question_text=test_question,
                question_type="regulatory_compliance",
                user_context={"industry": "technology", "size": "small"},
            )
            end_time = time.time()

            response_time = end_time - start_time
            print("✅ Cache test completed:")
            print(f"   Response time: {response_time:.2f} seconds")
            print(f"   Likely cached: {'Yes' if response_time < 1.0 else 'No'}\n")
        except Exception as e:
            print(f"❌ Cache test failed: {e}\n")

    print("🎉 AI functionality tests completed!")


if __name__ == "__main__":
    asyncio.run(test_ai_functionality())
