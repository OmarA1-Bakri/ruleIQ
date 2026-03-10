#!/bin/bash
# Doppler Neo4j AuraDB Configuration with Credentials

echo "🔐 Configuring Doppler with Neo4j AuraDB Credentials"
echo "===================================================="
echo ""

# Check if Doppler CLI is installed
if ! command -v doppler &> /dev/null; then
    echo "❌ Doppler CLI not found. Please install it first:"
    echo "   curl -Ls --tlsv1.2 --proto \"=https\" --retry 3 https://cli.doppler.com/install.sh | sudo sh"
    exit 1
fi

# Check if logged in
if ! doppler configure get token &> /dev/null; then
    echo "⚠️  Not logged into Doppler. Please run: doppler login"
    exit 1
fi

echo "📝 Setting Neo4j AuraDB credentials in Doppler..."
echo ""

# Set the actual credentials
doppler secrets set NEO4J_URI="neo4j+s://YOUR_INSTANCE_ID.databases.neo4j.io" --silent
doppler secrets set NEO4J_USERNAME="neo4j" --silent
doppler secrets set NEO4J_PASSWORD="YOUR_NEO4J_PASSWORD" --silent
doppler secrets set NEO4J_DATABASE="neo4j" --silent
doppler secrets set NEO4J_INSTANCE_ID="YOUR_NEO4J_INSTANCE_ID" --silent
doppler secrets set NEO4J_QUERY_API_URL="https://YOUR_INSTANCE_ID.databases.neo4j.io/db/neo4j/query/v2" --silent

echo "✅ Doppler secrets configured successfully!"
echo ""

# Test the connection
echo "🔍 Testing AuraDB connection..."
echo ""

doppler run -- python3 -c "
import os
import sys
from neo4j import GraphDatabase

uri = os.getenv('NEO4J_URI')
username = os.getenv('NEO4J_USERNAME')
password = os.getenv('NEO4J_PASSWORD')

print(f'Connecting to: {uri}')

try:
    driver = GraphDatabase.driver(uri, auth=(username, password))
    with driver.session() as session:
        # Test basic connectivity
        result = session.run('RETURN 1 as test')
        if result.single()['test'] == 1:
            print('✅ Successfully connected to AuraDB!')
            print('')
            
            # Get database statistics
            try:
                node_count = session.run('MATCH (n) RETURN count(n) as count').single()['count']
                rel_count = session.run('MATCH ()-[r]->() RETURN count(r) as count').single()['count']
                
                print('📊 Database Statistics:')
                print(f'   Nodes: {node_count:,}')
                print(f'   Relationships: {rel_count:,}')
                
                # Check for any existing data
                labels_result = session.run('CALL db.labels() YIELD label RETURN collect(label) as labels')
                labels = labels_result.single()['labels']
                if labels:
                    print(f'   Node Labels: {', '.join(labels[:5])}{'...' if len(labels) > 5 else ''}')
                
                rel_types_result = session.run('CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) as types')
                rel_types = rel_types_result.single()['types']
                if rel_types:
                    print(f'   Relationship Types: {', '.join(rel_types[:5])}{'...' if len(rel_types) > 5 else ''}')
                    
            except Exception as stats_error:
                print(f'   (Could not retrieve statistics: {stats_error})')
            
    driver.close()
    sys.exit(0)
    
except Exception as e:
    print(f'❌ Connection failed: {e}')
    print('')
    print('Troubleshooting steps:')
    print('1. Check if the AuraDB instance is active (not paused)')
    print('2. Verify network connectivity to neo4j.io')
    print('3. Try accessing the instance at: https://console.neo4j.io')
    sys.exit(1)
" 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Configuration complete! Your application is connected to AuraDB."
    echo ""
    echo "📌 Doppler Configuration Summary:"
    echo "   Environment: $(doppler configure get config)"
    echo "   Project: $(doppler configure get project)"
    echo ""
    echo "📌 To run your application:"
    echo "   doppler run -- uvicorn api.main:app --host 0.0.0.0 --port 8000"
    echo ""
    echo "📌 To view all Neo4j secrets:"
    echo "   doppler secrets get NEO4J_URI NEO4J_USERNAME NEO4J_DATABASE NEO4J_INSTANCE_ID"
    echo ""
    echo "⚠️  Security Note: This script contains sensitive credentials."
    echo "   Consider deleting it after successful configuration:"
    echo "   rm scripts/doppler-neo4j-configure.sh"
else
    echo ""
    echo "⚠️  Configuration saved but connection test failed."
    echo "   The AuraDB instance might be paused or initializing."
fi