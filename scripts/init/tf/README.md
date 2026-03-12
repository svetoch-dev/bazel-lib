# Cloud Infrastructure Creation

This step provisions all required cloud infrastructure components using **Terraform**. The process ensures the environment is fully prepared for application deployment.

## Resources Created

- Storage buckets  
- Networking components  
- Kubernetes clusters  
- IAM roles  
- Container registries  

## Workflow Overview

### ⚙️ Preparation

Execute cloud-specific initialization steps required before provisioning.

### 🗂️ Terraform State Setup

Create a cloud-specific Terraform backend to manage remote state.

### 🚀 Apply Infrastructure

Apply all Terraform modules across environments listed in `terraform.tfvars.json`.

### 🔐 Import Secrets

Import sensitive data required by infrastructure-level applications (e.g., credentials, tokens).

### 🧹 Post-Steps

Clean up and remove any unused folders to maintain a tidy project structure.

