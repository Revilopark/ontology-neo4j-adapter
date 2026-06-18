# Ontology Neo4j Aura Adapter

A typed vocabulary + constraint system for representing knowledge as a verifiable graph, 
with Neo4j Aura deployment support.

Based on the ClawHub skill `@oswalpalash/ontology`.

## Architecture

```
Ontology (Local JSONL)  -->  Neo4j Aura (Cloud Graph DB)
     |                              |
     v                              v
  graph.jsonl                 Nodes + Relations
  schema.yaml                 Constraints + Indexes
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
export NEO4J_URI="neo4j+s://xxxxx.databases.neo4j.io"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"
```

### 3. Initialize Neo4j Schema

```bash
python3 src/neo4j_adapter.py init --uri $NEO4J_URI --password $NEO4J_PASSWORD
```

### 4. Create Local Ontology Entities

```bash
python3 scripts/ontology.py create --type Person --props '{"name":"Alice","email":"alice@example.com"}'
python3 scripts/ontology.py create --type Project --props '{"name":"Website Redesign","status":"active"}'
python3 scripts/ontology.py relate --from proj_xxx --rel has_owner --to p_xxx
```

### 5. Sync to Neo4j Aura

```bash
python3 src/neo4j_adapter.py sync --uri $NEO4J_URI --password $NEO4J_PASSWORD
```

## Core Types

- **Person**: name, email?, phone?, notes?
- **Organization**: name, type?, members[]
- **Project**: name, status, goals[], owner?
- **Task**: title, status, due?, priority?, assignee?, blockers[]
- **Event**: title, start, end?, location?, attendees[], recurrence?
- **Document**: title, path?, url?, summary?
- **Note**: content, tags[], refs[]
- **Credential**: service, secret_ref (forbidden: password, secret, token)

## Neo4j Aura Optimizations

- Connection pool lifetime < 300s (Aura requirement)
- Encrypted Bolt protocol (neo4j+s://)
- Automatic schema constraints (unique IDs, type indexes)
- Batch sync from JSONL to Neo4j

## License

MIT - Based on @oswalpalash/ontology from ClawHub


## Vertex AI GraphRAG

Query your knowledge graph with semantic search powered by Vertex AI embeddings:

```bash
python3 src/vertex_graphrag.py \
  --neo4j-uri neo4j+s://xxxxx.databases.neo4j.io \
  --neo4j-password your-password \
  --query "Alice" \
  --vertex-project your-gcp-project
```

Features:
- Multi-hop graph traversal (depth 1-3)
- Semantic relevance ranking with embeddings
- Subgraph context extraction
- Vertex AI Gemini integration for content generation

## Content Creator

Generate structured content from your knowledge graph:

```bash
# Project status report
python3 src/content_creator.py create \
  --template project_report \
  --subject "Website Redesign" \
  --neo4j-uri ... --neo4j-password ... \
  --output report.md

# Meeting agenda
python3 src/content_creator.py create \
  --template meeting_agenda \
  --subject "Team Sync" \
  --neo4j-uri ... --neo4j-password ... \
  --output agenda.md

# List available templates
python3 src/content_creator.py list-templates \
  --neo4j-uri ... --neo4j-password ...
```

Available Templates:
- `project_report` - Status report with tasks, blockers, owners
- `task_plan` - Actionable plan with priorities and dependencies
- `person_summary` - Professional profile from graph data
- `meeting_agenda` - Agenda from Event + attendees + tasks
- `knowledge_digest` - Weekly digest of new/changed entities
- `onboarding_guide` - Team onboarding for new members
- `custom` - Custom content with your own prompt

## Unified CLI

All tools accessible from one entry point:

```bash
python3 scripts/ontology_cli.py <command> [args]

# Commands:
ontology_cli.py ontology create --type Person --props '{"name":"Alice"}'
ontology_cli.py neo4j sync --uri ... --password ...
ontology_cli.py graphrag --neo4j-uri ... --query "Alice"
ontology_cli.py content create --template project_report --subject "Website Redesign"
```
