#!/usr/bin/env python3
"""
Content Creator - Generate structured content from ontology knowledge graph.
Uses Vertex AI GraphRAG to create reports, summaries, task plans, and documentation.
"""

import json
import os
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Optional

# Import our GraphRAG module
try:
    from src.vertex_graphrag import VertexGraphRAG, GraphContext
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.vertex_graphrag import VertexGraphRAG, GraphContext


class ContentCreator:
    """
    Content creation system powered by ontology knowledge graph + AI.

    Templates:
    - project_report: Status report for a project with tasks, blockers, owners
    - task_plan: Actionable plan from goals and dependencies
    - person_summary: Profile summary from Person entity + related work
    - meeting_agenda: Agenda from Event + attendees + related tasks
    - knowledge_digest: Weekly digest of new entities and changes
    - onboarding_guide: Guide for new team members
    """

    TEMPLATES = {
        "project_report": {
            "description": "Project status report with tasks, blockers, and owners",
            "query": "Project {name}",
            "prompt": """Generate a comprehensive project status report including:
1. Executive summary (2-3 sentences)
2. Current status and progress
3. Key tasks with status breakdown (open/in-progress/blocked/done)
4. Blockers and dependencies
5. Team members and their roles
6. Risks and recommendations
7. Next milestones

Use the knowledge graph context to provide specific, accurate details."""
        },

        "task_plan": {
            "description": "Actionable task plan with priorities and dependencies",
            "query": "Task {name} OR Goal {name}",
            "prompt": """Create an actionable task plan:
1. Objective statement
2. Task breakdown with priority order
3. Dependencies between tasks (what blocks what)
4. Estimated effort for each task
5. Assigned owners (from graph)
6. Due dates and milestones
7. Success criteria
8. Risk mitigation

Format as a markdown checklist with specific assignees."""
        },

        "person_summary": {
            "description": "Professional profile summary from graph data",
            "query": "Person {name}",
            "prompt": """Generate a professional profile summary:
1. Name and role
2. Current projects and responsibilities
3. Key skills and expertise
4. Recent accomplishments
5. Active tasks and priorities
6. Team collaborations
7. Contact information
8. Availability status

Keep it concise but informative (200-300 words)."""
        },

        "meeting_agenda": {
            "description": "Meeting agenda from Event entity + related work",
            "query": "Event {name}",
            "prompt": """Create a structured meeting agenda:
1. Meeting title, date, time, location
2. Attendees and their roles
3. Agenda items (with time allocations)
4. Pre-read materials (documents from graph)
5. Discussion topics with context
6. Decisions needed
7. Action items from previous related meetings
8. Post-meeting follow-up tasks

Format as a professional meeting agenda document."""
        },

        "knowledge_digest": {
            "description": "Weekly digest of new/changed entities in the graph",
            "query": "*",
            "prompt": """Generate a weekly knowledge digest:
1. New entities added this week (by type)
2. Updated projects and their status changes
3. New tasks and assignments
4. Completed milestones
5. New relationships formed
6. Key insights from the graph
7. Upcoming deadlines (next 7 days)
8. Recommended follow-ups

Format as a newsletter-style digest with sections and bullet points.""",
            "filter_recent": True
        },

        "onboarding_guide": {
            "description": "Team onboarding guide for new members",
            "query": "Organization {name} OR Project {name}",
            "prompt": """Create an onboarding guide:
1. Welcome message and team overview
2. Key people to meet (with roles)
3. Active projects and how to contribute
4. Important tools and accounts
5. Team policies and procedures
6. First-week checklist
7. Common questions answered
8. Resources and documentation

Make it friendly and practical for a new team member."""
        },

        "custom": {
            "description": "Custom content with user-provided prompt",
            "query": "{name}",
            "prompt": None  # User provides
        }
    }

    def __init__(self, neo4j_uri: str, neo4j_password: str,
                 neo4j_user: str = "neo4j",
                 vertex_project: Optional[str] = None):
        """Initialize content creator with GraphRAG backend."""
        self.rag = VertexGraphRAG(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            vertex_project=vertex_project
        )

    def close(self):
        """Close connections."""
        self.rag.close()

    def create(self, template: str, subject: str = None,
               custom_prompt: str = None, entity_types: List[str] = None,
               output_format: str = "markdown") -> Dict:
        """
        Generate content using a template.

        Args:
            template: Template name from TEMPLATES
            subject: Entity name to focus on (e.g., project name, person name)
            custom_prompt: For "custom" template, the generation prompt
            entity_types: Filter graph query by entity types
            output_format: Output format (markdown, json, html)

        Returns:
            Dict with generated content and metadata
        """
        if template not in self.TEMPLATES:
            raise ValueError(f"Unknown template: {template}. Available: {list(self.TEMPLATES.keys())}")

        template_def = self.TEMPLATES[template]

        # Build query from template
        if subject:
            query = template_def["query"].replace("{name}", subject)
        else:
            query = template_def["query"].replace("{name}", "*")

        # Get generation prompt
        prompt = custom_prompt or template_def.get("prompt", f"Summarize information about: {query}")

        # Retrieve graph context and generate
        result = self.rag.query_and_generate(
            query=query,
            generation_prompt=prompt,
            entity_types=entity_types,
            max_depth=3
        )

        # Format output
        if output_format == "markdown":
            formatted = self._format_markdown(result, template, subject)
        elif output_format == "json":
            formatted = json.dumps(result, indent=2, default=str)
        elif output_format == "html":
            formatted = self._format_html(result, template, subject)
        else:
            formatted = result["generated_content"]

        return {
            "template": template,
            "subject": subject,
            "output_format": output_format,
            "content": formatted,
            "raw_result": result,
            "generated_at": datetime.now().isoformat()
        }

    def _format_markdown(self, result: Dict, template: str, subject: str) -> str:
        """Format result as markdown document."""
        ctx = result.get("context", {})

        header = f"""# {self.TEMPLATES[template]['description']}

**Subject:** {subject or "General"}  
**Generated:** {result.get('timestamp', datetime.now().isoformat())}  
**Model:** {result.get('model', 'unknown')}  
**Graph Entities:** {ctx.get('entity_count', 0)} | **Relations:** {ctx.get('relation_count', 0)}

---

"""

        body = result.get("generated_content", "No content generated.")

        footer = f"""

---

*Generated from ontology knowledge graph via Vertex AI GraphRAG*  
*Relevance Score: {ctx.get('relevance_score', 0):.2f}*
"""

        return header + body + footer

    def _format_html(self, result: Dict, template: str, subject: str) -> str:
        """Format result as HTML document."""
        ctx = result.get("context", {})
        content = result.get("generated_content", "No content generated.")

        # Convert markdown-like content to HTML (simple conversion)
        html_content = content.replace("

", "</p><p>").replace("
", "<br>")
        html_content = f"<p>{html_content}</p>"

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.TEMPLATES[template]['description']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .meta {{ color: #666; font-size: 0.9em; border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-bottom: 20px; }}
        .content {{ line-height: 1.6; }}
        .footer {{ margin-top: 30px; padding-top: 10px; border-top: 1px solid #ddd; color: #999; font-size: 0.8em; }}
    </style>
</head>
<body>
    <h1>{self.TEMPLATES[template]['description']}</h1>
    <div class="meta">
        <strong>Subject:</strong> {subject or "General"}<br>
        <strong>Generated:</strong> {result.get('timestamp', datetime.now().isoformat())}<br>
        <strong>Model:</strong> {result.get('model', 'unknown')}<br>
        <strong>Graph Entities:</strong> {ctx.get('entity_count', 0)} | 
        <strong>Relations:</strong> {ctx.get('relation_count', 0)}
    </div>
    <div class="content">
        {html_content}
    </div>
    <div class="footer">
        Generated from ontology knowledge graph via Vertex AI GraphRAG<br>
        Relevance Score: {ctx.get('relevance_score', 0):.2f}
    </div>
</body>
</html>"""

    def list_templates(self) -> Dict:
        """List available content templates."""
        return {
            name: {"description": t["description"], "requires_subject": "{name}" in t["query"]}
            for name, t in self.TEMPLATES.items()
        }


def main():
    parser = argparse.ArgumentParser(description="Content Creator from Ontology Graph")
    parser.add_argument("--neo4j-uri", required=True, help="Neo4j URI")
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j username")
    parser.add_argument("--neo4j-password", required=True, help="Neo4j password")
    parser.add_argument("--vertex-project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"), help="GCP project ID")

    subparsers = parser.add_subparsers(dest="command")

    # create
    create_parser = subparsers.add_parser("create", help="Create content")
    create_parser.add_argument("--template", required=True, choices=list(ContentCreator.TEMPLATES.keys()),
                                help="Content template")
    create_parser.add_argument("--subject", help="Entity name to focus on")
    create_parser.add_argument("--prompt", help="Custom prompt (for 'custom' template)")
    create_parser.add_argument("--types", help="Comma-separated entity types")
    create_parser.add_argument("--format", default="markdown", choices=["markdown", "json", "html"],
                                help="Output format")
    create_parser.add_argument("--output", help="Output file (default: stdout)")

    # list-templates
    subparsers.add_parser("list-templates", help="List available templates")

    args = parser.parse_args()

    creator = ContentCreator(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        vertex_project=args.vertex_project
    )

    try:
        if args.command == "create":
            entity_types = args.types.split(",") if args.types else None
            result = creator.create(
                template=args.template,
                subject=args.subject,
                custom_prompt=args.prompt,
                entity_types=entity_types,
                output_format=args.format
            )

            output = result["content"]
            if args.output:
                with open(args.output, "w") as f:
                    f.write(output)
                print(f"Content written to: {args.output}")
            else:
                print(output)

        elif args.command == "list-templates":
            templates = creator.list_templates()
            print(json.dumps(templates, indent=2))

        else:
            parser.print_help()
    finally:
        creator.close()


if __name__ == "__main__":
    main()
