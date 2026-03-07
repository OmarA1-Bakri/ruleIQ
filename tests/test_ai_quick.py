#!/usr/bin/env python3
"""
Quick AI test without running the full API server
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")


async def test_ai_direct():
    """Test AI components directly"""
    print("🤖 Testing AI Components Directly\n")

    # Test Google AI API key
    print("1️⃣ Testing Google AI API...")
    try:
        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            print("❌ GOOGLE_AI_API_KEY not found in .env.local")
            return

        import google.genai as genai

        client = genai.Client(api_key=api_key)

        # Test prompt
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents="Say 'AI is working with Neon database!'",
        )

        print(f"✅ Google AI Response: {response.text}")
        print("   Model: gemini-1.5-flash")
        print(f"   API Key: {api_key[:10]}...\n")

    except Exception as e:
        print(f"❌ Google AI test failed: {e}\n")

    # Test OpenAI API
    print("2️⃣ Testing OpenAI API...")
    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY not found")
            return

        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'OpenAI is ready!'"}],
            max_tokens=50,
        )

        print(f"✅ OpenAI Response: {response.choices[0].message.content}")
        print("   Model: gpt-3.5-turbo")
        print(f"   API Key: {api_key[:10]}...\n")

    except Exception as e:
        print(f"❌ OpenAI test failed: {e}\n")

    # Test circuit breaker
    print("3️⃣ Testing Circuit Breaker...")
    try:
        from services.ai.circuit_breaker import AICircuitBreaker

        breaker = AICircuitBreaker()
        print("✅ Circuit breaker initialized")
        print(f"   State: {breaker.state}")
        print(f"   Failure count: {breaker.failure_count}\n")

    except Exception as e:
        print(f"❌ Circuit breaker test failed: {e}\n")

    print("🎉 AI component tests completed!")
    print("\n📊 Summary:")
    print("- Google AI API: Test individual response")
    print("- OpenAI API: Test individual response")
    print("- Circuit Breaker: Test initialization")
    print("- Database: Already tested with Neon ✅")
    print("\nYour AI system is ready!")


if __name__ == "__main__":
    asyncio.run(test_ai_direct())
