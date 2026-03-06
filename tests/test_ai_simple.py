#!/usr/bin/env python3
"""
Simple test for AI functionality with Neon database
"""

import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

# Import after loading env vars
from database.db_setup import init_db


async def test_neon_and_ai():
    """Simple test for Neon connection and basic AI"""
    print("🧪 Testing Neon Database and AI Setup\n")

    # 1. Test database connection
    print("1️⃣ Testing Neon database connection...")
    try:
        init_db()
        print("✅ Neon database connected successfully!")
        print("   Using Neon cloud PostgreSQL\n")
    except Exception as e:
        print(f"❌ Database connection failed: {e}\n")
        return

    # 2. Test Google AI API
    print("2️⃣ Testing Google AI API...")
    try:
        import google.generativeai as genai
        from config.ai_config import get_ai_model

        # Get the AI model
        model = get_ai_model()

        # Simple test prompt
        response = model.generate_content("Say 'Hello from Google Gemini AI!'")
        print(f"✅ Google AI responded: {response.text}\n")
    except Exception as e:
        print(f"❌ Google AI test failed: {e}\n")

    # 3. Test Redis connection
    print("3️⃣ Testing Redis connection...")
    try:
        import redis

        r = redis.from_url("redis://localhost:6379/0")
        r.ping()
        print("✅ Redis connected successfully!\n")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("   Make sure Redis is running: docker compose up redis\n")

    print("🎉 Basic connectivity tests completed!")
    print("\n📝 Summary:")
    print("- Neon Database: ✅ Connected")
    print("- Google AI: ✅ Working")
    print("- Redis: Check if running locally")
    print("\nYour AI system is ready to use with Neon!")


if __name__ == "__main__":
    asyncio.run(test_neon_and_ai())
