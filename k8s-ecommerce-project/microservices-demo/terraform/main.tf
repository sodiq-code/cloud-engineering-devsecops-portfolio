# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Definition of local variables
locals {
  base_apis = [
    "container.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
    "cloudprofiler.googleapis.com"
  ]
  memorystore_apis = ["redis.googleapis.com"]
  cluster_name     = google_container_cluster.my_cluster.name
}

# Enable Google Cloud APIs
#checkov:skip=CKV_TF_1:Module sourced from Terraform Registry with a pinned semantic version; git-commit pinning not applicable to registry sources in this portfolio environment
module "enable_google_apis" {
  source  = "terraform-google-modules/project-factory/google//modules/project_services"
  version = "~> 18.0"

  project_id                  = var.gcp_project_id
  disable_services_on_destroy = false

  # activate_apis is the set of base_apis and the APIs required by user-configured deployment options
  activate_apis = concat(local.base_apis, var.memorystore ? local.memorystore_apis : [])
}

# Create GKE cluster
#checkov:skip=CKV_GCP_12:GKE Autopilot manages network policy enforcement automatically; manual network_policy block is not supported in Autopilot mode
#checkov:skip=CKV_GCP_65:Authenticator groups config requires a Google Workspace domain not available in this portfolio environment
#checkov:skip=CKV_GCP_69:Workload metadata config is node-pool-level and managed by GKE Autopilot; not configurable on the cluster resource
resource "google_container_cluster" "my_cluster" {

  name     = var.name
  location = var.region

  # Enable autopilot for this cluster
  enable_autopilot = true

  # Set an empty ip_allocation_policy to allow autopilot cluster to spin up correctly
  ip_allocation_policy {
  }

  # Private nodes: hide node IPs from the public internet (CKV_GCP_25, CKV_GCP_64)
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false           # Keep public endpoint for kubectl access
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  # Restrict kubectl access to specific CIDR blocks (CKV_GCP_20)
  # IMPORTANT: Replace this placeholder CIDR with your actual public management IP(s) in production.
  # Using a private/minikube IP here is for portfolio demo purposes only.
  # Example for production: "203.0.113.10/32" (your office/VPN public IP)
  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = "192.168.49.2/32"       # Placeholder — replace with your public management IP
      display_name = "External Access"
    }
  }

  # Pin the cluster to the REGULAR release channel for security patches (CKV_GCP_70)
  release_channel {
    channel = "REGULAR"
  }

  # Disable client certificate authentication — use OIDC/RBAC instead (CKV_GCP_13)
  master_auth {
    client_certificate_config {
      issue_client_certificate = false
    }
  }

  # Enable Binary Authorization to only allow trusted container images (CKV_GCP_66)
  binary_authorization {
    evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE"
  }

  # Enable intranode visibility for VPC flow log coverage (CKV_GCP_61)
  enable_intranode_visibility = true

  # Avoid setting deletion_protection to false
  # until you're ready (and certain you want) to destroy the cluster.
  # deletion_protection = false

  depends_on = [
    module.enable_google_apis
  ]
}

# Get credentials for cluster
#checkov:skip=CKV_TF_1:Module sourced from Terraform Registry with a pinned semantic version; git-commit pinning not applicable to registry sources in this portfolio environment
module "gcloud" {
  source  = "terraform-google-modules/gcloud/google"
  version = "~> 4.0"

  platform              = "linux"
  additional_components = ["kubectl", "beta"]

  create_cmd_entrypoint = "gcloud"
  # Module does not support explicit dependency
  # Enforce implicit dependency through use of local variable
  create_cmd_body = "container clusters get-credentials ${local.cluster_name} --zone=${var.region} --project=${var.gcp_project_id}"
}

# Apply YAML kubernetes-manifest configurations
resource "null_resource" "apply_deployment" {
  provisioner "local-exec" {
    interpreter = ["bash", "-exc"]
    command     = "kubectl apply -k ${var.filepath_manifest} -n ${var.namespace}"
  }

  depends_on = [
    module.gcloud
  ]
}

# Wait condition for all Pods to be ready before finishing
resource "null_resource" "wait_conditions" {
  provisioner "local-exec" {
    interpreter = ["bash", "-exc"]
    command     = <<-EOT
    kubectl wait --for=condition=AVAILABLE apiservice/v1beta1.metrics.k8s.io --timeout=180s
    kubectl wait --for=condition=ready pods --all -n ${var.namespace} --timeout=280s
    EOT
  }

  depends_on = [
    resource.null_resource.apply_deployment
  ]
}
