#!/usr/bin/env python3
"""
Vertex AI GraphRAG Integration for Ontology Knowledge Graph
Combines Neo4j graph traversal with Vertex AI embeddings and Gemini for content generation.
"""

import json
import os
import sys
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Neo4j driver
try:
    from neo4j import GraphDatabase
except ImportError:
    print("ERROR: neo4j driver not installed. Run: pip install neo4j", file=sys.stderr)
    sys.exit(1)

# Vertex AI (optional - will use fallback if not available)
try:
    from google.cloud import aiplatform
    from vertexai.language_models import TextEmbeddingModel, TextGenerationModel
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False
    print("WARNING: Vertex AI SDK not installed. Using fallback embeddings.", file=sys.stderr)

# OpenAI fallback
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class GraphContext:
    """Structured context retrieved from the knowledge graph."""
    entities: List[Dict]
    relations: List[Dict]
    summary: str
    relevance_score: float


class VertexGraphRAG:
    """
    GraphRAG system combining Neo4j ontology with Vertex AI.

    Architecture:
    1. Query Neo4j for relevant subgraph
    2. Generate embeddings for entities (Vertex AI or fallback)
    3. Rank by semantic relevance to query
    4. Feed context to LLM for content generation
    """

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str,
                 vertex_project: Optional[str] = None,
                 vertex_location: str = "us-central1",
                 embedding_model: str = "textembedding-gecko@003",
                 generation_model: str = "gemini-1.5-pro-002"):
        """
        Initialize GraphRAG system.

        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            vertex_project: GCP project ID (optional, auto-detected if in GCP)
            vertex_location: GCP region for Vertex AI
            embedding_model: Vertex AI embedding model name
            generation_model: Vertex AI generation model name
        """
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.vertex_location = vertex_location
        self.embedding_model_name = embedding_model
        self.generation_model_name = generation_model

        # Initialize Neo4j driver
        self.driver = GraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password)
        )

        # Initialize Vertex AI
        self.vertex_project = vertex_project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.embedding_model = None
        self.generation_model = None

        if VERTEX_AVAILABLE and self.vertex_project:
            try:
                aiplatform.init(project=self.vertex_project, location=vertex_location)
                self.embedding_model = TextEmbeddingModel.from_pretrained(embedding_model)
                self.generation_model = TextGenerationModel.from_pretrained(generation_model)
                print(f"Vertex AI initialized: project={self.vertex_project}, location={vertex_location}")
            except Exception as e:
                print(f"WARNING: Vertex AI init failed: {e}. Using fallback.", file=sys.stderr)

    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text using Vertex AI or fallback."""
        if self.embedding_model:
            try:
                embeddings = self.embedding_model.get_embeddings([text])
                return embeddings[0].values
            except Exception as e:
                print(f"Embedding failed: {e}. Using fallback.", file=sys.stderr)

        # Fallback: simple keyword-based pseudo-embedding
        # In production, replace with OpenAI or local model
        return self._fallback_embedding(text)

    def _fallback_embedding(self, text: str) -> List[float]:
        """Simple keyword hashing fallback embedding."""
        import hashlib
        # Create a simple 128-dim embedding from text hash
        hash_val = hashlib.md5(text.lower().encode()).hexdigest()
        # Convert to floats in range [-1, 1]
        embedding = []
        for i in range(0, 32, 2):
            val = int(hash_val[i:i+2], 16) / 128.0 - 1.0
            embedding.append(val)
        # Pad to 128 dimensions
        embedding = embedding * 4
        return embedding[:128]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def retrieve_subgraph(self, query: str, entity_types: List[str] = None,
                         max_depth: int = 2, max_entities: int = 20) -> GraphContext:
        """
        Retrieve relevant subgraph from Neo4j based on query.

        Uses multi-hop traversal starting from entities matching the query.
        """
        # Step 1: Find seed entities matching query (by name or property)
        where_clause = ""
        params = {"query": f"(?i).*{query}.*"}

        if entity_types:
            where_clause = "AND e.type IN $types"
            params["types"] = entity_types

        cypher = f"""
            MATCH (e:Entity)
            WHERE (e.name =~ $query OR e.title =~ $query OR e.description =~ $query
                   OR e.content =~ $query OR e.id =~ $query)
            {where_clause}
            RETURN e.id as id, e.type as type, e as properties
            LIMIT 10
        """

        with self.driver.session() as session:
            seed_results = session.run(cypher, **params)
            seed_entities = [dict(record) for record in seed_results]

        if not seed_entities:
            # Fallback: return recent entities
            cypher = """
                MATCH (e:Entity)
                RETURN e.id as id, e.type as type, e as properties
                ORDER BY e.created DESC
                LIMIT 20
            """
            with self.driver.session() as session:
                seed_results = session.run(cypher)
                seed_entities = [dict(record) for record in seed_results]

        # Step 2: Expand subgraph from seeds
        all_entity_ids = {e["id"] for e in seed_entities}
        all_entities = seed_entities.copy()
        all_relations = []

        for depth in range(max_depth):
            if not all_entity_ids:
                break

            # Find neighbors
            cypher = """
                MATCH (e:Entity)-[r]->(neighbor:Entity)
                WHERE e.id IN $ids AND NOT neighbor.id IN $all_ids
                RETURN e.id as from_id, neighbor.id as id, neighbor.type as type,
                       neighbor as properties, type(r) as rel_type, r as rel_props
                LIMIT $limit
            """

            with self.driver.session() as session:
                neighbors = session.run(cypher, ids=list(all_entity_ids),
                                       all_ids=list(all_entity_ids), limit=max_entities)
                new_entities = []
                for record in neighbors:
                    all_relations.append({
                        "from": record["from_id"],
                        "to": record["id"],
                        "type": record["rel_type"],
                        "properties": dict(record["rel_props"]) if record["rel_props"] else {}
                    })
                    if record["id"] not in all_entity_ids:
                        new_entities.append({
                            "id": record["id"],
                            "type": record["type"],
                            "properties": dict(record["properties"]) if record["properties"] else {}
                        })
                        all_entity_ids.add(record["id"])

                all_entities.extend(new_entities)
                if len(all_entities) >= max_entities:
                    break

        # Step 3: Rank by semantic relevance to query
        query_embedding = self._get_embedding(query)

        for entity in all_entities:
            # Create text representation for embedding
            props = entity.get("properties", {})
            text_repr = f"{entity.get('type', '')}: "
            if isinstance(props, dict):
                text_repr += " ".join(str(v) for v in props.values() if isinstance(v, str))
            else:
                text_repr += str(props)

            entity_embedding = self._get_embedding(text_repr)
            entity["relevance"] = self._cosine_similarity(query_embedding, entity_embedding)

        # Sort by relevance
        all_entities.sort(key=lambda x: x.get("relevance", 0), reverse=True)

        # Generate summary
        summary = self._generate_summary(all_entities, all_relations, query)

        avg_relevance = sum(e.get("relevance", 0) for e in all_entities) / len(all_entities) if all_entities else 0

        return GraphContext(
            entities=all_entities[:max_entities],
            relations=all_relations,
            summary=summary,
            relevance_score=avg_relevance
        )

    def _generate_summary(self, entities: List[Dict], relations: List[Dict], query: str) -> str:
        """Generate a natural language summary of the subgraph."""
        entity_summary = []
        for e in entities[:10]:
            props = e.get("properties", {})
            if isinstance(props, dict):
                name = props.get("name") or props.get("title") or props.get("content", "")[:50]
            else:
                name = str(props)[:50]
            entity_summary.append(f"- {e.get('type', 'Entity')} {e.get('id', '')}: {name}")

        relation_summary = []
        for r in relations[:10]:
            relation_summary.append(f"- {r['from']} --[{r['type']}]--> {r['to']}")

        summary = f"""Knowledge Graph Context for: "{query}"

Entities ({len(entities)} total):
{chr(10).join(entity_summary)}

Relations ({len(relations)} total):
{chr(10).join(relation_summary)}
"""
        return summary

    def generate_content(self, prompt: str, context: GraphContext = None,
                        max_tokens: int = 1024, temperature: float = 0.7) -> str:
        """
        Generate content using Vertex AI Gemini or fallback.

        Args:
            prompt: User prompt for content generation
            context: Optional GraphContext from retrieve_subgraph()
            max_tokens: Maximum output tokens
            temperature: Creativity parameter (0.0-1.0)

        Returns:
            Generated content string
        """
        # Build augmented prompt with graph context
        if context:
            augmented_prompt = f"""Based on the following knowledge graph context, {prompt}

KNOWLEDGE GRAPH CONTEXT:
{context.summary}

Please use the entities and relationships above to inform your response.
Be specific about the people, projects, tasks, and events mentioned.
"""
        else:
            augmented_prompt = prompt

        if self.generation_model:
            try:
                response = self.generation_model.predict(
                    augmented_prompt,
                    max_output_tokens=max_tokens,
                    temperature=temperature
                )
                return response.text
            except Exception as e:
                print(f"Vertex AI generation failed: {e}. Using fallback.", file=sys.stderr)

        # Fallback: return structured context as "generated content"
        return f"""[FALLBACK GENERATION - Vertex AI not available]

Query: {prompt}

{context.summary if context else "No graph context available."}

To enable AI generation, configure Vertex AI:
1. Install: pip install google-cloud-aiplatform
2. Set GOOGLE_CLOUD_PROJECT environment variable
3. Authenticate: gcloud auth application-default login
"""

    def query_and_generate(self, query: str, generation_prompt: str = None,
                          entity_types: List[str] = None,
                          max_depth: int = 2) -> Dict:
        """
        Full GraphRAG pipeline: retrieve subgraph + generate content.

        Args:
            query: Search query for graph retrieval
            generation_prompt: Optional specific prompt for generation
            entity_types: Filter by entity types
            max_depth: Graph traversal depth

        Returns:
            Dict with context, generated_content, and metadata
        """
        # Retrieve relevant subgraph
        context = self.retrieve_subgraph(query, entity_types, max_depth)

        # Generate content
        prompt = generation_prompt or f"Explain what we know about '{query}' and suggest next steps."
        generated = self.generate_content(prompt, context)

        return {
            "query": query,
            "context": {
                "entity_count": len(context.entities),
                "relation_count": len(context.relations),
                "summary": context.summary,
                "relevance_score": context.relevance_score
            },
            "generated_content": generated,
            "timestamp": datetime.now().isoformat(),
            "model": self.generation_model_name if self.generation_model else "fallback"
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Vertex AI GraphRAG for Ontology")
    parser.add_argument("--neo4j-uri", required=True, help="Neo4j URI")
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j username")
    parser.add_argument("--neo4j-password", required=True, help="Neo4j password")
    parser.add_argument("--vertex-project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"), help="GCP project ID")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--prompt", help="Generation prompt (defaults to query explanation)")
    parser.add_argument("--types", help="Comma-separated entity types to filter")
    parser.add_argument("--depth", type=int, default=2, help="Graph traversal depth")

    args = parser.parse_args()

    rag = VertexGraphRAG(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        vertex_project=args.vertex_project
    )

    try:
        entity_types = args.types.split(",") if args.types else None
        result = rag.query_and_generate(
            query=args.query,
            generation_prompt=args.prompt,
            entity_types=entity_types,
            max_depth=args.depth
        )
        print(json.dumps(result, indent=2, default=str))
    finally:
        rag.close()


if __name__ == "__main__":
    main()
