#!/usr/bin/env python3
"""
Neo4j Aura Adapter for Ontology Knowledge Graph
Maps ontology entities/relations to Neo4j nodes/relationships.
Optimized for Neo4j Aura with connection pool settings.
"""

import json
import os
import sys
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# Neo4j driver (install: pip install neo4j)
try:
    from neo4j import GraphDatabase, basic_auth
    from neo4j.exceptions import ServiceUnavailable, AuthError
except ImportError:
    print("ERROR: neo4j driver not installed. Run: pip install neo4j", file=sys.stderr)
    sys.exit(1)

class OntologyNeo4jAdapter:
    """Adapter to sync ontology graph with Neo4j Aura."""

    def __init__(self, uri: str, username: str, password: str):
        """
        Initialize connection to Neo4j Aura.

        Args:
            uri: Neo4j Aura URI (e.g., neo4j+s://xxxxx.databases.neo4j.io)
            username: Usually 'neo4j'
            password: Instance password
        """
        self.uri = uri
        self.username = username
        self.password = password

        # Aura-optimized connection settings
        # Connection pool lifetime must be < 300s for Aura
        self.driver = GraphDatabase.driver(
            uri,
            auth=basic_auth(username, password),
            connection_acquisition_timeout=60,
            connection_timeout=30,
            max_connection_pool_size=50,
            connection_pool_min_size=1,
            connection_pool_max_size=50,
            # For Aura: connection must be refreshed before 300s
            connection_pool_timeout=300,
            # Encrypted by default for Aura (neo4j+s://)
            encrypted=True if "+s" in uri or "+ssc" in uri else None,
        )

        # Verify connectivity
        try:
            self.driver.verify_connectivity()
            print(f"Connected to Neo4j Aura: {uri}")
        except ServiceUnavailable as e:
            print(f"ERROR: Cannot connect to Neo4j Aura: {e}", file=sys.stderr)
            sys.exit(1)
        except AuthError as e:
            print(f"ERROR: Authentication failed: {e}", file=sys.stderr)
            sys.exit(1)

    def close(self):
        """Close the driver connection."""
        if self.driver:
            self.driver.close()

    def init_schema(self):
        """Initialize Neo4j schema constraints and indexes for ontology."""
        with self.driver.session() as session:
            # Create constraints for unique entity IDs
            session.run("""
                CREATE CONSTRAINT entity_id IF NOT EXISTS
                FOR (e:Entity) REQUIRE e.id IS UNIQUE
            """)

            # Create index on entity type for fast queries
            session.run("""
                CREATE INDEX entity_type IF NOT EXISTS
                FOR (e:Entity) ON (e.type)
            """)

            # Create index on relation type
            session.run("""
                CREATE INDEX relation_type IF NOT EXISTS
                FOR ()-[r:RELATES]->() ON (r.relation_type)
            """)

            print("Schema initialized (constraints + indexes)")

    def sync_entity(self, entity: Dict) -> bool:
        """Sync a single ontology entity to Neo4j as a node."""
        entity_id = entity.get("id")
        entity_type = entity.get("type")
        properties = entity.get("properties", {})
        created = entity.get("created", datetime.now().isoformat())
        updated = entity.get("updated", datetime.now().isoformat())

        # Flatten properties for Neo4j
        props = {
            "id": entity_id,
            "type": entity_type,
            "created": created,
            "updated": updated,
            **properties
        }

        # Convert lists to JSON strings for Neo4j compatibility
        for key, value in props.items():
            if isinstance(value, list):
                props[key] = json.dumps(value)

        cypher = """
            MERGE (e:Entity {id: $id})
            SET e.type = $type,
                e.created = $created,
                e.updated = $updated
            SET e += $properties
            RETURN e
        """

        with self.driver.session() as session:
            result = session.run(cypher, id=entity_id, type=entity_type, 
                               created=created, updated=updated, properties=props)
            return result.single() is not None

    def sync_relation(self, relation: Dict) -> bool:
        """Sync a single ontology relation to Neo4j as a relationship."""
        from_id = relation.get("from")
        to_id = relation.get("to")
        rel_type = relation.get("rel")
        properties = relation.get("properties", {})
        created = relation.get("created", datetime.now().isoformat())

        # Sanitize relation type for Neo4j (must be uppercase, no special chars)
        safe_rel_type = self._sanitize_rel_type(rel_type)

        props = {
            "relation_type": rel_type,
            "created": created,
            **properties
        }

        cypher = f"""
            MATCH (from:Entity {{id: $from_id}})
            MATCH (to:Entity {{id: $to_id}})
            MERGE (from)-[r:{safe_rel_type}]->(to)
            SET r += $properties
            RETURN r
        """

        with self.driver.session() as session:
            try:
                result = session.run(cypher, from_id=from_id, to_id=to_id, properties=props)
                return result.single() is not None
            except Exception as e:
                print(f"ERROR syncing relation {from_id}-[{rel_type}]->{to_id}: {e}", file=sys.stderr)
                return False

    def _sanitize_rel_type(self, rel_type: str) -> str:
        """Sanitize relation type for Neo4j Cypher."""
        # Replace special chars with underscore, uppercase
        safe = rel_type.upper().replace("-", "_").replace(" ", "_")
        # Remove any non-alphanumeric chars except underscore
        safe = "".join(c if c.isalnum() or c == "_" else "_" for c in safe)
        return safe

    def sync_graph(self, graph_path: str = "memory/ontology/graph.jsonl") -> Tuple[int, int]:
        """Sync entire ontology graph to Neo4j Aura."""
        if not os.path.exists(graph_path):
            print(f"Graph file not found: {graph_path}")
            return 0, 0

        entities = []
        relations = []

        with open(graph_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("op") == "create" and "entity" in entry:
                        entities.append(entry["entity"])
                    elif entry.get("op") == "relate":
                        relations.append(entry)
                except json.JSONDecodeError:
                    continue

        # Sync entities first (nodes must exist before relations)
        entity_count = 0
        for entity in entities:
            if self.sync_entity(entity):
                entity_count += 1

        print(f"Synced {entity_count}/{len(entities)} entities")

        # Then sync relations
        relation_count = 0
        for relation in relations:
            if self.sync_relation(relation):
                relation_count += 1

        print(f"Synced {relation_count}/{len(relations)} relations")
        return entity_count, relation_count

    def query_entities(self, entity_type: str = None, where: Dict = None) -> List[Dict]:
        """Query entities from Neo4j."""
        where_clause = ""
        params = {}

        if entity_type:
            where_clause += "WHERE e.type = $type "
            params["type"] = entity_type

        if where:
            for key, value in where.items():
                where_clause += f"AND e.{key} = ${key} "
                params[key] = value

        cypher = f"""
            MATCH (e:Entity)
            {where_clause}
            RETURN e.id as id, e.type as type, e as properties
            LIMIT 1000
        """

        with self.driver.session() as session:
            results = session.run(cypher, **params)
            return [dict(record) for record in results]

    def query_related(self, entity_id: str, rel_type: str = None) -> List[Dict]:
        """Query entities related to a given entity."""
        rel_filter = f"WHERE type(r) = '{self._sanitize_rel_type(rel_type)}'" if rel_type else ""

        cypher = f"""
            MATCH (e:Entity {{id: $id}})-[r]->(related:Entity)
            {rel_filter}
            RETURN related.id as id, related.type as type, related as properties, type(r) as relation
        """

        with self.driver.session() as session:
            results = session.run(cypher, id=entity_id)
            return [dict(record) for record in results]

    def get_stats(self) -> Dict:
        """Get database statistics."""
        with self.driver.session() as session:
            # Count entities by type
            entity_result = session.run("""
                MATCH (e:Entity)
                RETURN e.type as type, count(e) as count
            """)
            entities = {record["type"]: record["count"] for record in entity_result}

            # Count relations by type
            rel_result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
            """)
            relations = {record["type"]: record["count"] for record in rel_result}

            return {
                "entities": entities,
                "relations": relations,
                "total_entities": sum(entities.values()),
                "total_relations": sum(relations.values())
            }

    def clear_database(self, confirm: bool = False):
        """WARNING: Clear all data from Neo4j database."""
        if not confirm:
            print("WARNING: This will delete ALL data. Set confirm=True to proceed.")
            return

        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("Database cleared.")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Neo4j Aura Ontology Adapter")
    subparsers = parser.add_subparsers(dest="command")

    # Common args
    parser.add_argument("--uri", default=os.environ.get("NEO4J_URI"), help="Neo4j URI")
    parser.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"), help="Username")
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"), help="Password")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize schema")

    # sync
    sync_parser = subparsers.add_parser("sync", help="Sync graph to Neo4j")
    sync_parser.add_argument("--graph", default="memory/ontology/graph.jsonl", help="Graph file path")

    # query
    query_parser = subparsers.add_parser("query", help="Query entities")
    query_parser.add_argument("--type", help="Entity type")
    query_parser.add_argument("--where", default="{}", help="JSON where clause")

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show database stats")

    # clear
    clear_parser = subparsers.add_parser("clear", help="Clear database (DANGER)")
    clear_parser.add_argument("--confirm", action="store_true", help="Confirm deletion")

    args = parser.parse_args()

    if not args.uri or not args.password:
        print("ERROR: --uri and --password required (or set NEO4J_URI and NEO4J_PASSWORD env vars)", file=sys.stderr)
        sys.exit(1)

    adapter = OntologyNeo4jAdapter(args.uri, args.user, args.password)

    try:
        if args.command == "init":
            adapter.init_schema()
        elif args.command == "sync":
            adapter.sync_graph(args.graph)
        elif args.command == "query":
            where = json.loads(args.where)
            results = adapter.query_entities(args.type, where)
            print(json.dumps(results, indent=2, default=str))
        elif args.command == "stats":
            stats = adapter.get_stats()
            print(json.dumps(stats, indent=2, default=str))
        elif args.command == "clear":
            adapter.clear_database(args.confirm)
        else:
            parser.print_help()
    finally:
        adapter.close()

if __name__ == "__main__":
    main()
