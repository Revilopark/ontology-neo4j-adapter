#!/bin/bash
# Example: Complete workflow from ontology to content creation

set -e

# Configuration
NEO4J_URI="neo4j+s://xxxxx.databases.neo4j.io"
NEO4J_PASSWORD="your-password"
VERTEX_PROJECT="your-gcp-project"

# 1. Create ontology entities
echo "=== Creating Ontology Entities ==="
python3 scripts/ontology.py create --type Person --props '{"name":"Alice","email":"alice@example.com"}'
python3 scripts/ontology.py create --type Project --props '{"name":"Website Redesign","status":"active"}'
python3 scripts/ontology.py create --type Task --props '{"title":"Design homepage","status":"in_progress","priority":"high"}'

# 2. Create relations (use actual IDs from step 1 output)
# python3 scripts/ontology.py relate --from <project_id> --rel has_owner --to <person_id>
# python3 scripts/ontology.py relate --from <project_id> --rel has_task --to <task_id>

# 3. Sync to Neo4j Aura
echo "=== Syncing to Neo4j Aura ==="
python3 src/neo4j_adapter.py init --uri $NEO4J_URI --password $NEO4J_PASSWORD
python3 src/neo4j_adapter.py sync --uri $NEO4J_URI --password $NEO4J_PASSWORD

# 4. GraphRAG query
echo "=== GraphRAG Query ==="
python3 src/vertex_graphrag.py \
  --neo4j-uri $NEO4J_URI \
  --neo4j-password $NEO4J_PASSWORD \
  --query "Alice" \
  --vertex-project $VERTEX_PROJECT

# 5. Generate content
echo "=== Generating Content ==="
python3 src/content_creator.py create \
  --template project_report \
  --subject "Website Redesign" \
  --neo4j-uri $NEO4J_URI \
  --neo4j-password $NEO4J_PASSWORD \
  --vertex-project $VERTEX_PROJECT \
  --output report.md

echo "Done! Check report.md for generated content."
