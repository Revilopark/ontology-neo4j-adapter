terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.2.0"
}

# Variables
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP Zone"
  type        = string
  default     = "us-central1-a"
}

variable "neo4j_password" {
  description = "Neo4j admin password (min 8 chars)"
  type        = string
  sensitive   = true
}

variable "instance_name" {
  description = "Name for the Neo4j deployment"
  type        = string
  default     = "ontology-neo4j"
}

variable "machine_type" {
  description = "GCP machine type"
  type        = string
  default     = "e2-medium"
}

variable "disk_size" {
  description = "Disk size in GB"
  type        = number
  default     = 50
}

# Provider configuration
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# Create VPC network
resource "google_compute_network" "neo4j_vpc" {
  name                    = "${var.instance_name}-vpc"
  auto_create_subnetworks = false
}

# Create subnetwork
resource "google_compute_subnetwork" "neo4j_subnet" {
  name          = "${var.instance_name}-subnet"
  ip_cidr_range = "10.0.0.0/24"
  network       = google_compute_network.neo4j_vpc.id
  region        = var.region
}

# Firewall rule - allow Neo4j ports
resource "google_compute_firewall" "neo4j_external" {
  name    = "${var.instance_name}-allow-neo4j"
  network = google_compute_network.neo4j_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["7474", "7473", "7687", "22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["neo4j"]
}

# Firewall rule - internal traffic
resource "google_compute_firewall" "neo4j_internal" {
  name    = "${var.instance_name}-allow-internal"
  network = google_compute_network.neo4j_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.0.0.0/24"]
  target_tags   = ["neo4j"]
}

# Neo4j startup script
locals {
  startup_script = templatefile("${path.module}/startup.sh", {
    neo4j_password = var.neo4j_password
  })
}

# Compute instance for Neo4j Community Edition
resource "google_compute_instance" "neo4j" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone

  tags = ["neo4j"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = var.disk_size
      type  = "pd-ssd"
    }
  }

  network_interface {
    network    = google_compute_network.neo4j_vpc.id
    subnetwork = google_compute_subnetwork.neo4j_subnet.id

    access_config {
      # Ephemeral public IP
    }
  }

  metadata = {
    startup-script = local.startup_script
  }

  service_account {
    scopes = ["cloud-platform"]
  }

  labels = {
    environment = "ontology"
    managed_by  = "terraform"
  }
}

# Output the external IP
output "neo4j_external_ip" {
  description = "External IP of the Neo4j instance"
  value       = google_compute_instance.neo4j.network_interface[0].access_config[0].nat_ip
}

output "neo4j_bolt_url" {
  description = "Neo4j Bolt URL"
  value       = "neo4j://${google_compute_instance.neo4j.network_interface[0].access_config[0].nat_ip}:7687"
}

output "neo4j_browser_url" {
  description = "Neo4j Browser URL"
  value       = "http://${google_compute_instance.neo4j.network_interface[0].access_config[0].nat_ip}:7474"
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = "gcloud compute ssh ${google_compute_instance.neo4j.name} --zone=${var.zone} --project=${var.project_id}"
}
