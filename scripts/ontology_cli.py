#!/usr/bin/env python3
"""
Ontology Neo4j Aura - Unified CLI
Ontology management + Neo4j sync + Vertex AI GraphRAG + Content Creation
"""

import sys
import os
import argparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def ontology_cli():
    """Run the ontology CLI."""
    from ontology import main
    main()

def neo4j_cli():
    """Run the Neo4j adapter CLI."""
    from neo4j_adapter import main
    main()

def graphrag_cli():
    """Run the Vertex AI GraphRAG CLI."""
    from vertex_graphrag import main
    main()

def content_cli():
    """Run the content creator CLI."""
    from content_creator import main
    main()

def main():
    parser = argparse.ArgumentParser(
        description="Ontology Neo4j Aura - Unified Knowledge Graph CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  ontology     Manage local ontology entities and relations
  neo4j        Sync ontology to Neo4j Aura database
  graphrag     Query graph with Vertex AI embeddings
  content      Generate content from knowledge graph

Examples:
  # Create a person entity
  %(prog)s ontology create --type Person --props '{"name":"Alice"}'

  # Sync to Neo4j Aura
  %(prog)s neo4j sync --uri neo4j+s://xxxxx.databases.neo4j.io --password xxx

  # GraphRAG query
  %(prog)s graphrag --neo4j-uri ... --neo4j-password ... --query "Alice"

  # Generate project report
  %(prog)s content create --template project_report --subject "Website Redesign" \
    --neo4j-uri ... --neo4j-password ...
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Add placeholder subparsers (actual parsing handled by imported modules)
    subparsers.add_parser("ontology", help="Local ontology management")
    subparsers.add_parser("neo4j", help="Neo4j Aura sync")
    subparsers.add_parser("graphrag", help="Vertex AI GraphRAG")
    subparsers.add_parser("content", help="Content creation from graph")

    # Parse only the first level
    args, remaining = parser.parse_known_args()

    # Pass remaining args to the appropriate module
    sys.argv = [sys.argv[0]] + remaining

    if args.command == "ontology":
        ontology_cli()
    elif args.command == "neo4j":
        neo4j_cli()
    elif args.command == "graphrag":
        graphrag_cli()
    elif args.command == "content":
        content_cli()
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
