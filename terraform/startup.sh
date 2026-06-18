#!/bin/bash
set -e

# Update system
apt-get update
apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release software-properties-common

# Install Java 17 (required for Neo4j 5.x)
apt-get install -y openjdk-17-jdk

# Add Neo4j repository
curl -fsSL https://debian.neo4j.com/neotechnology.gpg.key | gpg --dearmor -o /usr/share/keyrings/neo4j.gpg
echo "deb [signed-by=/usr/share/keyrings/neo4j.gpg] https://debian.neo4j.com stable 5" | tee /etc/apt/sources.list.d/neo4j.list
apt-get update

# Install Neo4j Community Edition
apt-get install -y neo4j

# Configure Neo4j
NEO4J_PASSWORD="${neo4j_password}"

# Set initial password
neo4j-admin dbms set-initial-password "$NEO4J_PASSWORD"

# Enable remote connections
sed -i 's/#server.default_listen_address=0.0.0.0/server.default_listen_address=0.0.0.0/' /etc/neo4j/neo4j.conf
sed -i 's/#server.bolt.listen_address=:7687/server.bolt.listen_address=0.0.0.0:7687/' /etc/neo4j/neo4j.conf
sed -i 's/#server.http.listen_address=:7474/server.http.listen_address=0.0.0.0:7474/' /etc/neo4j/neo4j.conf
sed -i 's/#server.https.listen_address=:7473/server.https.listen_address=0.0.0.0:7473/' /etc/neo4j/neo4j.conf

# Enable APOC plugin (for JSON import and graph algorithms)
echo "dbms.plugins.directory=/var/lib/neo4j/plugins" >> /etc/neo4j/neo4j.conf

# Start Neo4j
systemctl enable neo4j
systemctl start neo4j

# Wait for Neo4j to be ready
sleep 30

# Verify Neo4j is running
if systemctl is-active --quiet neo4j; then
    echo "Neo4j is running successfully"
    echo "Bolt URL: bolt://$(curl -s ifconfig.me):7687"
    echo "Browser URL: http://$(curl -s ifconfig.me):7474"
else
    echo "Neo4j failed to start"
    journalctl -u neo4j -n 50
    exit 1
fi
