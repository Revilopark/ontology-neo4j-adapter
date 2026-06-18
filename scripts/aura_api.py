#!/usr/bin/env python3
"""
Neo4j Aura API Automation Script
Creates and manages Aura instances via the official API.
Requires: Aura API credentials (Client ID + Client Secret)
Note: Free tier users need billing info or marketplace project for API access.
"""

import requests
import json
import sys
import os
import argparse
import base64
from typing import Dict, Optional

class AuraAPIClient:
    """Client for Neo4j Aura API v1."""

    BASE_URL = "https://api.neo4j.io/v1"
    TOKEN_URL = "https://api.neo4j.io/oauth/token"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self._authenticate()

    def _authenticate(self):
        """Obtain OAuth2 bearer token."""
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        response = requests.post(
            self.TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={"grant_type": "client_credentials"},
            timeout=30
        )

        if response.status_code != 200:
            print(f"Authentication failed: {response.text}", file=sys.stderr)
            sys.exit(1)

        self.access_token = response.json()["access_token"]
        print("Authenticated with Aura API")

    def _headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def get_tenants(self) -> list:
        """Get list of projects (tenants)."""
        response = requests.get(
            f"{self.BASE_URL}/tenants",
            headers=self._headers(),
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("data", [])

    def create_instance(self, tenant_id: str, name: str, region: str = "europe-west1",
                       memory: str = "8GB", instance_type: str = "professional-db",
                       cloud_provider: str = "gcp", version: str = "5") -> Dict:
        """Create a new AuraDB instance."""
        payload = {
            "version": version,
            "region": region,
            "memory": memory,
            "name": name,
            "type": instance_type,
            "tenant_id": tenant_id,
            "cloud_provider": cloud_provider
        }

        response = requests.post(
            f"{self.BASE_URL}/instances",
            headers=self._headers(),
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def get_instance(self, instance_id: str) -> Dict:
        """Get instance details including connection URI."""
        response = requests.get(
            f"{self.BASE_URL}/instances/{instance_id}",
            headers=self._headers(),
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def list_instances(self) -> list:
        """List all instances."""
        response = requests.get(
            f"{self.BASE_URL}/instances",
            headers=self._headers(),
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("data", [])

    def delete_instance(self, instance_id: str):
        """Delete an instance."""
        response = requests.delete(
            f"{self.BASE_URL}/instances/{instance_id}",
            headers=self._headers(),
            timeout=30
        )
        response.raise_for_status()
        return response.status_code == 202


def main():
    parser = argparse.ArgumentParser(description="Neo4j Aura API Automation")
    parser.add_argument("--client-id", default=os.environ.get("AURA_CLIENT_ID"), help="Aura API Client ID")
    parser.add_argument("--client-secret", default=os.environ.get("AURA_CLIENT_SECRET"), help="Aura API Client Secret")

    subparsers = parser.add_subparsers(dest="command")

    # list-tenants
    subparsers.add_parser("list-tenants", help="List projects")

    # list-instances
    subparsers.add_parser("list-instances", help="List instances")

    # create
    create_parser = subparsers.add_parser("create", help="Create instance")
    create_parser.add_argument("--tenant-id", required=True, help="Project/Tenant ID")
    create_parser.add_argument("--name", required=True, help="Instance name")
    create_parser.add_argument("--region", default="us-central1", help="Region")
    create_parser.add_argument("--memory", default="8GB", help="Memory size")
    create_parser.add_argument("--type", default="professional-db", help="Instance type")
    create_parser.add_argument("--cloud", default="gcp", help="Cloud provider")

    # get
    get_parser = subparsers.add_parser("get", help="Get instance details")
    get_parser.add_argument("--id", required=True, help="Instance ID")

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete instance")
    delete_parser.add_argument("--id", required=True, help="Instance ID")

    args = parser.parse_args()

    if not args.client_id or not args.client_secret:
        print("ERROR: --client-id and --client-secret required", file=sys.stderr)
        sys.exit(1)

    client = AuraAPIClient(args.client_id, args.client_secret)

    if args.command == "list-tenants":
        tenants = client.get_tenants()
        print(json.dumps(tenants, indent=2))

    elif args.command == "list-instances":
        instances = client.list_instances()
        print(json.dumps(instances, indent=2))

    elif args.command == "create":
        result = client.create_instance(
            tenant_id=args.tenant_id,
            name=args.name,
            region=args.region,
            memory=args.memory,
            instance_type=args.type,
            cloud_provider=args.cloud
        )
        print(json.dumps(result, indent=2))

    elif args.command == "get":
        result = client.get_instance(args.id)
        print(json.dumps(result, indent=2))

    elif args.command == "delete":
        if client.delete_instance(args.id):
            print(f"Instance {args.id} deletion initiated")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
