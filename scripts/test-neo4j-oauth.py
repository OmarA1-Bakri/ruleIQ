#!/usr/bin/env python3
"""
Test Neo4j AuraDB connection using OAuth authentication.
"""

import os
import requests
import base64
from neo4j import GraphDatabase


def get_oauth_token():
    """Get OAuth token using client credentials."""
    client_id = os.getenv("NEO4J_CLIENT_ID")
    client_secret = os.getenv("NEO4J_CLIENT_SECRET")

    token_url = "https://aura-api.eu.auth0.com/oauth/token"

    # Create auth header
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {"grant_type": "client_credentials", "audience": "https://console.neo4j.io"}

    response = requests.post(token_url, headers=headers, data=data)

    if response.status_code == 200:
        token_data = response.json()
        return token_data["access_token"]
    else:
        raise Exception(f"Failed to get token: {response.text}")


def test_query_api(token):
    """Test the Query API with OAuth token."""
    query_api_url = os.getenv("NEO4J_QUERY_API_URL")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    query = {"statement": "RETURN 1 as test", "parameters": {}}

    response = requests.post(query_api_url, json=query, headers=headers)

    print(f"Query API Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Query API working!")
        return True
    else:
        print(f"Response: {response.text}")
        return False


def test_driver_connection():
    """Test standard driver connection."""
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            if result.single()["test"] == 1:
                print("✅ Driver connection working!")
                return True
        driver.close()
    except Exception as e:
        print(f"❌ Driver connection failed: {e}")

        # Try with the OAuth token as password
        print("\nTrying with OAuth token as password...")
        try:
            token = get_oauth_token()
            driver = GraphDatabase.driver(uri, auth=("neo4j", token))
            with driver.session() as session:
                result = session.run("RETURN 1 as test")
                if result.single()["test"] == 1:
                    print("✅ Driver connection working with OAuth token!")
                    return True
            driver.close()
        except Exception as e2:
            print(f"❌ OAuth token auth also failed: {e2}")
            return False


def main():
    print("🔍 Testing Neo4j AuraDB Authentication")
    print("=" * 40)

    # Show configuration
    print("\n📋 Configuration:")
    print(f"URI: {os.getenv('NEO4J_URI')}")
    print(f"Client Name: {os.getenv('NEO4J_CLIENT_NAME')}")
    print(f"Client ID: {os.getenv('NEO4J_CLIENT_ID')[:10]}...")
    print(f"Instance ID: {os.getenv('NEO4J_INSTANCE_ID')[:10]}...")

    # Get OAuth token
    print("\n1️⃣ Getting OAuth Token...")
    try:
        token = get_oauth_token()
        print(f"✅ Token obtained: {token[:50]}...")

        # Test Query API
        print("\n2️⃣ Testing Query API...")
        test_query_api(token)

    except Exception as e:
        print(f"❌ OAuth failed: {e}")

    # Test driver connection
    print("\n3️⃣ Testing Driver Connection...")
    test_driver_connection()

    print("\n" + "=" * 40)
    print("📌 Recommendations:")
    print("1. Check Neo4j Aura console for correct password")
    print("2. Ensure instance is not paused")
    print("3. May need to reset password in console")


if __name__ == "__main__":
    main()
