# Ontology → Neo4j Aura Deployment Guide

## Overview

This guide covers deploying the ontology knowledge graph to Neo4j on Google Cloud Platform.

## Three Deployment Options

### Option 1: Neo4j Aura Free (Recommended for Testing)

**Zero infrastructure, fully managed, always free.**

1. Go to [console.neo4j.io](https://console.neo4j.io)
2. Create free account (no credit card)
3. Create "AuraDB Free" instance
4. Download credentials file (contains URI, username, password)
5. Set environment variables:
   ```bash
   export NEO4J_URI="neo4j+s://xxxxx.databases.neo4j.io"
   export NEO4J_USER="neo4j"
   export NEO4J_PASSWORD="your-password"
   ```
6. Sync ontology:
   ```bash
   python3 src/neo4j_adapter.py sync --uri $NEO4J_URI --password $NEO4J_PASSWORD
   ```

**Limitations:**
- 200,000 nodes / 400,000 relationships max
- Paused after 72h inactivity (auto-resume on access)
- No API access for instance creation (must use web console)

### Option 2: Neo4j Aura Professional/Enterprise (Production)

**Fully managed, scalable, API-accessible.**

Available via:
- [Neo4j Aura Console](https://console.neo4j.io) (direct)
- [Google Cloud Marketplace](https://console.cloud.google.com/marketplace) (pay-as-you-go with GCP billing)

**API Automation:**
```bash
# Requires API credentials (Account Settings → API Keys in Aura Console)
export AURA_CLIENT_ID="your-client-id"
export AURA_CLIENT_SECRET="your-client-secret"

# List projects
python3 scripts/aura_api.py list-tenants --client-id $AURA_CLIENT_ID --client-secret $AURA_CLIENT_SECRET

# Create instance
python3 scripts/aura_api.py create \
  --client-id $AURA_CLIENT_ID \
  --client-secret $AURA_CLIENT_SECRET \
  --tenant-id $TENANT_ID \
  --name "ontology-graph" \
  --region us-central1 \
  --memory 8GB \
  --type professional-db \
  --cloud gcp
```

### Option 3: Self-Managed on Google Cloud (Full Control)

**Deploy Neo4j Community Edition on GCP Compute Engine.**

```bash
cd terraform

# Set variables
cp terraform.tfvars.example terraform.tfvars
# Edit: project_id, neo4j_password

# Deploy
terraform init
terraform plan
terraform apply

# Get connection details
terraform output neo4j_bolt_url
terraform output neo4j_browser_url
```

## Google Cloud Vertex AI Integration

Neo4j integrates with Vertex AI for GraphRAG (Graph Retrieval-Augmented Generation):

```python
from src.neo4j_adapter import OntologyNeo4jAdapter
from google.cloud import aiplatform

# Initialize Vertex AI
aiplatform.init(project="your-gcp-project", location="us-central1")

# Connect to Neo4j
adapter = OntologyNeo4jAdapter(
    uri="neo4j+s://xxxxx.databases.neo4j.io",
    username="neo4j",
    password="your-password"
)

# Query graph for RAG context
context = adapter.query_related("entity_id", "has_task")
# Use context with Vertex AI embeddings
```

## Security Best Practices

1. **Never commit credentials** — Use `.env` files (ignored by git)
2. **Use Google Cloud Secret Manager** for production secrets
3. **Restrict firewall rules** — Change `0.0.0.0/0` to your IP in Terraform
4. **Enable HTTPS** — Always use `neo4j+s://` for Aura connections
5. **Rotate passwords** — Use Aura's auto-rotating tokens for API access

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Connection refused" | Check firewall rules / Aura instance is running |
| "Authentication failed" | Verify password / reset in Aura Console |
| "TLS connection error" | Use `neo4j+s://` not `bolt://` for Aura |
| "API credentials disabled" | Free tier requires billing info for API access |
| "Instance paused" | Free tier auto-pauses; click "Resume" in console |

## References

- [Neo4j Aura Docs](https://neo4j.com/docs/aura/)
- [Aura API Tutorial](https://neo4j.com/docs/aura/tutorials/create-auradb-instance-from-terminal/)
- [GCP Marketplace Neo4j](https://neo4j.com/blog/graph-database/neo4j-google-cloud-marketplace-listings/)
- [Neo4j + Vertex AI](https://neo4j.com/blog/genai/use-graphs-for-smarter-ai-with-neo4j-and-google-cloud-vertex-ai/)
