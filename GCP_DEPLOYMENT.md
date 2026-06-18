# Deploy Neo4j on Google Cloud (Marketplace or Terraform)

## Option 1: Google Cloud Marketplace (Easiest)

Neo4j Aura is available directly on Google Cloud Marketplace with click-to-deploy:

1. Visit [Google Cloud Marketplace - Neo4j Aura](https://console.cloud.google.com/marketplace/product/neo4j-public/neo4j-aura)
2. Select your project and click "Configure"
3. Choose tier: Professional or Business Critical
4. Configure instance name, region, and credentials
5. Deploy

## Option 2: Terraform (Self-Managed Community Edition)

For full control over the deployment:

```bash
cd terraform

# Copy and edit variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your GCP project ID and Neo4j password

# Initialize Terraform
terraform init

# Plan deployment
terraform plan

# Apply deployment
terraform apply

# Get connection details
terraform output neo4j_bolt_url
terraform output neo4j_browser_url
```

## Option 3: Neo4j Aura Free (Zero Infrastructure)

1. Go to [console.neo4j.io](https://console.neo4j.io)
2. Create free account (no credit card)
3. Create "AuraDB Free" instance
4. Copy the connection URI and password
5. Set environment variables:
   ```bash
   export NEO4J_URI="neo4j+s://xxxxx.databases.neo4j.io"
   export NEO4J_PASSWORD="your-password"
   ```

## Vertex AI Integration

Neo4j integrates with Google Cloud Vertex AI for GraphRAG:

1. Deploy Neo4j (Aura or self-managed)
2. Install Vertex AI SDK: `pip install google-cloud-aiplatform`
3. Use the `neo4j_adapter.py` with Vertex AI embeddings:
   ```python
   from src.neo4j_adapter import OntologyNeo4jAdapter
   from vertexai.language_models import TextEmbeddingModel

   adapter = OntologyNeo4jAdapter(uri, user, password)
   # Sync ontology entities with embeddings
   ```

## Security Notes

- The Terraform firewall rules allow connections from `0.0.0.0/0` (anywhere)
- **For production**: Restrict `source_ranges` to your IP in `terraform/main.tf`
- Always use HTTPS/Bolt+S for remote connections
- Store credentials in Google Cloud Secret Manager, not in files
