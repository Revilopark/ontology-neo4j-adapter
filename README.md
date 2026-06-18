# Ontology Neo4j Aura Adapter — DEPLOYED ✅

**Repository:** https://github.com/Revilopark/ontology-neo4j-adapter  
**Status:** Live with sample data (15 entities, 19 relations)  
**Version:** 1.0.0  
**Deployed:** 2026-06-18

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Revilopark/ontology-neo4j-adapter.git
cd ontology-neo4j-adapter

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set credentials (get from Neo4j Aura console)
export NEO4J_URI="neo4j+s://xxxxx.databases.neo4j.io"
export NEO4J_PASSWORD="your-password"

# 4. Sync sample data to Neo4j Aura
python3 src/neo4j_adapter.py init --uri $NEO4J_URI --password $NEO4J_PASSWORD
python3 src/neo4j_adapter.py sync --uri $NEO4J_URI --password $NEO4J_PASSWORD

# 5. Query with GraphRAG
python3 src/vertex_graphrag.py --neo4j-uri $NEO4J_URI --neo4j-password $NEO4J_PASSWORD --query "Alice"

# 6. Generate content
python3 src/content_creator.py create --template project_report --subject "Neo4j Migration" \
  --neo4j-uri $NEO4J_URI --neo4j-password $NEO4J_PASSWORD --output report.md
```

## Architecture

```
Ontology CLI (Local JSONL) → Neo4j Adapter → Neo4j Aura (Cloud Graph)
                                      ↓
                              Vertex AI GraphRAG
                                      ↓
                              Content Creator
                              (Reports/Plans/Agendas)
```

## What's Included

| Component | File | Description |
|-----------|------|-------------|
| **Core Ontology** | `scripts/ontology.py` | Entity/relation CRUD, validation, schema |
| **Neo4j Adapter** | `src/neo4j_adapter.py` | Sync to Neo4j Aura, query, stats |
| **Vertex AI GraphRAG** | `src/vertex_graphrag.py` | Semantic search, multi-hop traversal |
| **Content Creator** | `src/content_creator.py` | Generate reports, plans, agendas |
| **Aura API** | `scripts/aura_api.py` | Programmatic instance management |
| **Unified CLI** | `scripts/ontology_cli.py` | Single entry point |
| **GCP Terraform** | `terraform/` | Deploy Neo4j CE on Google Compute Engine |
| **GitHub Actions** | `.github/workflows/` | CI/CD automation |

## Sample Data

The repository includes a validated knowledge graph with:
- **15 entities**: 3 People, 2 Projects, 4 Tasks, 1 Organization, 1 Goal, 1 Event, 1 Document, 1 Note, 1 Device
- **19 relations**: ownership, task assignments, dependencies, attendance, hosting
- **Validation**: All constraints satisfied (no cycles, required fields present, no forbidden properties)

## Content Templates

- `project_report` — Status report with tasks, blockers, risks
- `task_plan` — Actionable plan with priorities and dependencies
- `person_summary` — Professional profile from graph data
- `meeting_agenda` — Agenda from Event + attendees + tasks
- `knowledge_digest` — Weekly digest of new/changed entities
- `onboarding_guide` — Team onboarding for new members
- `custom` — Any content with your own prompt

## Deployment Options

| Option | Cost | Setup | Best For |
|--------|------|-------|----------|
| **Aura Free** | $0 | Web console, 2 min | Testing, prototyping |
| **Aura Professional** | ~$65/mo | API or Marketplace | Production, team use |
| **GCP Self-Managed** | VM cost | Terraform | Full control, custom specs |

## Documentation

- `DEPLOYMENT_GUIDE.md` — Full deployment instructions
- `GCP_DEPLOYMENT.md` — Google Cloud specific setup
- `DEPLOYMENT_MANIFEST.json` — Machine-readable deployment spec
- `examples/workflow.sh` — Complete workflow example
- `examples/sample_report.md` — Sample generated content

## License

MIT — Based on @oswalpalash/ontology from ClawHub
