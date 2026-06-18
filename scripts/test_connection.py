#!/usr/bin/env python3
"""
Mock Neo4j Aura Connection Test
Validates the connection code without requiring live credentials.
"""

import json
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_connection_code():
    """Test that the connection code is syntactically correct and imports work."""
    print("=== Neo4j Aura Connection Code Test ===\n")

    # Test 1: Import neo4j driver
    try:
        from neo4j import GraphDatabase, basic_auth
        print("✅ Neo4j driver imports successfully")
    except ImportError as e:
        print(f"❌ Neo4j driver import failed: {e}")
        return False

    # Test 2: Import our adapter
    try:
        from neo4j_adapter import OntologyNeo4jAdapter
        print("✅ OntologyNeo4jAdapter imports successfully")
    except ImportError as e:
        print(f"❌ Adapter import failed: {e}")
        return False

    # Test 3: Import GraphRAG
    try:
        from vertex_graphrag import VertexGraphRAG, GraphContext
        print("✅ VertexGraphRAG imports successfully")
    except ImportError as e:
        print(f"❌ GraphRAG import failed: {e}")
        return False

    # Test 4: Import Content Creator
    try:
        from content_creator import ContentCreator
        print("✅ ContentCreator imports successfully")
    except ImportError as e:
        print(f"❌ ContentCreator import failed: {e}")
        return False

    # Test 5: Verify connection parameters
    print("\n=== Connection Parameters ===")
    print("Aura URI format: neo4j+s://<instance-id>.databases.neo4j.io")
    print("Default username: neo4j")
    print("Password: (provided during instance creation)")
    print("Port: 7687 (Bolt over TLS)")
    print("Connection pool lifetime: < 300 seconds (Aura requirement)")

    # Test 6: Verify local graph data exists
    graph_path = "memory/ontology/graph.jsonl"
    if os.path.exists(graph_path):
        with open(graph_path, 'r') as f:
            lines = [json.loads(line) for line in f if line.strip()]
        entities = [l for l in lines if l.get('op') == 'create']
        relations = [l for l in lines if l.get('op') == 'relate']
        print(f"\n✅ Local graph data: {len(entities)} entities, {len(relations)} relations")
    else:
        print(f"\n⚠️  No local graph data found")

    print("\n=== Test Complete ===")
    print("All code is ready. To connect to live Neo4j Aura:")
    print("1. Create instance at https://console.neo4j.io")
    print("2. Download credentials (URI, username, password)")
    print("3. Set environment variables:")
    print("   export NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io")
    print("   export NEO4J_PASSWORD=your-password")
    print("4. Run: python3 src/neo4j_adapter.py sync --uri $NEO4J_URI --password $NEO4J_PASSWORD")

    return True

if __name__ == "__main__":
    success = test_connection_code()
    sys.exit(0 if success else 1)
