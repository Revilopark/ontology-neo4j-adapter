#!/usr/bin/env python3
"""
Ontology - A typed vocabulary + constraint system for representing knowledge as a verifiable graph.
Adapted for Neo4j Aura deployment from ClawHub skill @oswalpalash/ontology.
"""

import json
import sys
import os
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional

# Default paths
GRAPH_PATH = os.environ.get("ONTOLOGY_GRAPH", "memory/ontology/graph.jsonl")
SCHEMA_PATH = os.environ.get("ONTOLOGY_SCHEMA", "memory/ontology/schema.yaml")

# Core types from the skill metadata
CORE_TYPES = {
    "Person": {"required": ["name"], "optional": ["email", "phone", "notes"]},
    "Organization": {"required": ["name"], "optional": ["type", "members"]},
    "Project": {"required": ["name", "status"], "optional": ["goals", "owner"]},
    "Task": {"required": ["title", "status"], "optional": ["due", "priority", "assignee", "blockers"]},
    "Goal": {"required": ["description"], "optional": ["target_date", "metrics"]},
    "Event": {"required": ["title", "start"], "optional": ["end", "location", "attendees", "recurrence"]},
    "Location": {"required": ["name"], "optional": ["address", "coordinates"]},
    "Document": {"required": ["title"], "optional": ["path", "url", "summary"]},
    "Message": {"required": ["content", "sender"], "optional": ["recipients", "thread"]},
    "Thread": {"required": ["subject", "participants"], "optional": ["messages"]},
    "Note": {"required": ["content"], "optional": ["tags", "refs"]},
    "Account": {"required": ["service", "username"], "optional": ["credential_ref"]},
    "Device": {"required": ["name", "type"], "optional": ["identifiers"]},
    "Credential": {"required": ["service", "secret_ref"], "optional": [], "forbidden": ["password", "secret", "token"]},
    "Action": {"required": ["type", "target"], "optional": ["timestamp", "outcome"]},
    "Policy": {"required": ["scope", "rule"], "optional": ["enforcement"]}
}

RELATION_CONSTRAINTS = {
    "has_owner": {"from_types": ["Project", "Task"], "to_types": ["Person"], "cardinality": "many_to_one"},
    "has_task": {"from_types": ["Project"], "to_types": ["Task"]},
    "blocks": {"from_types": ["Task"], "to_types": ["Task"], "acyclic": True},
    "attends": {"from_types": ["Person"], "to_types": ["Event"]},
    "located_at": {"from_types": ["Event", "Organization"], "to_types": ["Location"]},
    "has_member": {"from_types": ["Organization"], "to_types": ["Person"]},
    "has_goal": {"from_types": ["Project"], "to_types": ["Goal"]},
    "for_event": {"from_types": ["Task"], "to_types": ["Event"]},
    "has_project": {"from_types": ["Event"], "to_types": ["Project"]}
}

def ensure_dirs():
    os.makedirs(os.path.dirname(GRAPH_PATH) if os.path.dirname(GRAPH_PATH) else ".", exist_ok=True)

def generate_id(prefix: str) -> str:
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def load_graph() -> List[Dict]:
    if not os.path.exists(GRAPH_PATH):
        return []
    entries = []
    with open(GRAPH_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries

def append_entry(entry: Dict):
    ensure_dirs()
    with open(GRAPH_PATH, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")

def get_entities(graph: List[Dict], entity_type: str = None) -> List[Dict]:
    entities = []
    for entry in graph:
        if entry.get("op") == "create" and "entity" in entry:
            e = entry["entity"]
            if entity_type is None or e.get("type") == entity_type:
                entities.append(e)
    return entities

def get_relations(graph: List[Dict], from_id: str = None, rel_type: str = None, to_id: str = None) -> List[Dict]:
    relations = []
    for entry in graph:
        if entry.get("op") == "relate":
            r = entry
            if (from_id is None or r.get("from") == from_id) and \
               (rel_type is None or r.get("rel") == rel_type) and \
               (to_id is None or r.get("to") == to_id):
                relations.append(r)
    return relations

def validate_entity(entity: Dict, schema: Dict = None) -> tuple[bool, str]:
    entity_type = entity.get("type")
    if not entity_type:
        return False, "Entity must have a type"

    type_def = CORE_TYPES.get(entity_type)
    if not type_def:
        return False, f"Unknown type: {entity_type}"

    props = entity.get("properties", {})

    # Check required fields
    for req in type_def.get("required", []):
        if req not in props or props[req] is None:
            return False, f"Missing required property: {req}"

    # Check forbidden fields
    for forbidden in type_def.get("forbidden", []):
        if forbidden in props:
            return False, f"Forbidden property: {forbidden}"

    # Check Event end >= start
    if entity_type == "Event" and "end" in props and "start" in props:
        try:
            end_dt = datetime.fromisoformat(props["end"].replace("Z", "+00:00"))
            start_dt = datetime.fromisoformat(props["start"].replace("Z", "+00:00"))
            if end_dt < start_dt:
                return False, "Event end must be >= start"
        except:
            pass

    return True, "OK"

def validate_relation(graph: List[Dict], relation: Dict) -> tuple[bool, str]:
    rel_type = relation.get("rel")
    from_id = relation.get("from")
    to_id = relation.get("to")

    if not all([rel_type, from_id, to_id]):
        return False, "Relation must have rel, from, and to"

    # Find entities
    from_entity = None
    to_entity = None
    for entry in graph:
        if entry.get("op") == "create" and "entity" in entry:
            e = entry["entity"]
            if e.get("id") == from_id:
                from_entity = e
            if e.get("id") == to_id:
                to_entity = e

    if not from_entity:
        return False, f"Source entity not found: {from_id}"
    if not to_entity:
        return False, f"Target entity not found: {to_id}"

    # Check relation constraints
    constraint = RELATION_CONSTRAINTS.get(rel_type)
    if constraint:
        from_type = from_entity.get("type")
        to_type = to_entity.get("type")

        if from_type not in constraint.get("from_types", []):
            return False, f"Relation {rel_type} cannot start from {from_type}"
        if to_type not in constraint.get("to_types", []):
            return False, f"Relation {rel_type} cannot point to {to_type}"

        # Check acyclicity for blocks
        if constraint.get("acyclic"):
            if creates_cycle(graph, from_id, rel_type, to_id):
                return False, f"Relation {rel_type} would create a cycle"

    return True, "OK"

def creates_cycle(graph: List[Dict], from_id: str, rel_type: str, to_id: str) -> bool:
    """Check if adding this relation would create a cycle."""
    visited = set()
    stack = [to_id]
    while stack:
        current = stack.pop()
        if current == from_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        for r in get_relations(graph, rel_type=rel_type):
            if r.get("from") == current:
                stack.append(r.get("to"))
    return False

def cmd_create(args):
    entity_type = args.type
    props = json.loads(args.props) if args.props else {}

    if args.id:
        entity_id = args.id
    else:
        prefix = entity_type.lower()[:3]
        entity_id = generate_id(prefix)

    entity = {
        "id": entity_id,
        "type": entity_type,
        "properties": props,
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat()
    }

    valid, msg = validate_entity(entity)
    if not valid:
        print(f"VALIDATION ERROR: {msg}", file=sys.stderr)
        sys.exit(1)

    entry = {"op": "create", "entity": entity}
    append_entry(entry)
    print(json.dumps(entity, indent=2, default=str))
    return entity

def cmd_query(args):
    graph = load_graph()
    entity_type = args.type
    where_clause = json.loads(args.where) if args.where else {}

    results = get_entities(graph, entity_type)

    # Apply where filter
    filtered = []
    for e in results:
        props = e.get("properties", {})
        match = True
        for key, value in where_clause.items():
            if props.get(key) != value:
                match = False
                break
        if match:
            filtered.append(e)

    print(json.dumps(filtered, indent=2, default=str))
    return filtered

def cmd_get(args):
    graph = load_graph()
    for entry in graph:
        if entry.get("op") == "create" and "entity" in entry:
            e = entry["entity"]
            if e.get("id") == args.id:
                print(json.dumps(e, indent=2, default=str))
                return e
    print(f"Entity not found: {args.id}", file=sys.stderr)
    sys.exit(1)

def cmd_relate(args):
    graph = load_graph()
    relation = {
        "op": "relate",
        "from": args.from_id,
        "rel": args.rel,
        "to": args.to,
        "properties": json.loads(args.props) if args.props else {},
        "created": datetime.now().isoformat()
    }

    valid, msg = validate_relation(graph, relation)
    if not valid:
        print(f"VALIDATION ERROR: {msg}", file=sys.stderr)
        sys.exit(1)

    append_entry(relation)
    print(json.dumps(relation, indent=2, default=str))
    return relation

def cmd_related(args):
    graph = load_graph()
    relations = get_relations(graph, from_id=args.id, rel_type=args.rel)
    results = []
    for r in relations:
        for entry in graph:
            if entry.get("op") == "create" and "entity" in entry:
                e = entry["entity"]
                if e.get("id") == r.get("to"):
                    results.append(e)
    print(json.dumps(results, indent=2, default=str))
    return results

def cmd_list(args):
    graph = load_graph()
    results = get_entities(graph, args.type)
    print(json.dumps(results, indent=2, default=str))
    return results

def cmd_validate(args):
    graph = load_graph()
    errors = []

    # Validate all entities
    for entry in graph:
        if entry.get("op") == "create" and "entity" in entry:
            e = entry["entity"]
            valid, msg = validate_entity(e)
            if not valid:
                errors.append(f"Entity {e.get('id')}: {msg}")

    # Validate all relations
    for entry in graph:
        if entry.get("op") == "relate":
            valid, msg = validate_relation(graph, entry)
            if not valid:
                errors.append(f"Relation {entry.get('from')}->{entry.get('to')}: {msg}")

    if errors:
        print("VALIDATION ERRORS:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("All constraints satisfied.")

def cmd_schema_append(args):
    """Append schema definitions (placeholder for YAML merge)."""
    print("Schema append: Use direct file editing for schema.yaml")
    print(f"Schema path: {SCHEMA_PATH}")

def main():
    parser = argparse.ArgumentParser(description="Ontology - Knowledge Graph CLI")
    subparsers = parser.add_subparsers(dest="command")

    # create
    create_parser = subparsers.add_parser("create", help="Create an entity")
    create_parser.add_argument("--type", required=True, help="Entity type")
    create_parser.add_argument("--props", default="{}", help="JSON properties")
    create_parser.add_argument("--id", help="Optional ID (auto-generated if omitted)")

    # query
    query_parser = subparsers.add_parser("query", help="Query entities")
    query_parser.add_argument("--type", required=True, help="Entity type")
    query_parser.add_argument("--where", default="{}", help="JSON where clause")

    # get
    get_parser = subparsers.add_parser("get", help="Get entity by ID")
    get_parser.add_argument("--id", required=True, help="Entity ID")

    # relate
    relate_parser = subparsers.add_parser("relate", help="Create a relation")
    relate_parser.add_argument("--from", dest="from_id", required=True, help="Source entity ID")
    relate_parser.add_argument("--rel", required=True, help="Relation type")
    relate_parser.add_argument("--to", required=True, help="Target entity ID")
    relate_parser.add_argument("--props", default="{}", help="JSON properties")

    # related
    related_parser = subparsers.add_parser("related", help="Get related entities")
    related_parser.add_argument("--id", required=True, help="Entity ID")
    related_parser.add_argument("--rel", help="Relation type filter")

    # list
    list_parser = subparsers.add_parser("list", help="List entities by type")
    list_parser.add_argument("--type", required=True, help="Entity type")

    # validate
    validate_parser = subparsers.add_parser("validate", help="Validate all constraints")

    # schema-append
    schema_parser = subparsers.add_parser("schema-append", help="Append schema (manual)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "create": cmd_create,
        "query": cmd_query,
        "get": cmd_get,
        "relate": cmd_relate,
        "related": cmd_related,
        "list": cmd_list,
        "validate": cmd_validate,
        "schema-append": cmd_schema_append
    }

    commands[args.command](args)

if __name__ == "__main__":
    main()
