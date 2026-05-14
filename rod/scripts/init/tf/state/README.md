# 🗂️ Terraform State Setup

Create a cloud-specific Terraform backend to manage remote state effectively. This enables collaborative infrastructure management and state consistency.

## GCP Notes

For Google Cloud Platform, the Terraform state is stored in a **Google Cloud Storage (GCS)** bucket. The bucket is created with the following configuration:

- **Storage Class:** `STANDARD`  
- **Public Access Prevention:** Enabled  
- **Versioning:** Enabled  
- **Version Retention:** Keep the last 200 versions  

These settings help ensure durability, traceability, and security of the Terraform state files.

## Yandex Object Storage Notes

When `AWS_ENDPOINT_URL_S3` points to Yandex Object Storage, S3 Terraform
backends are created in Yandex Cloud. The setup grants the Terraform state
service account access to the bucket and initializes the secrets state object
from the backend key template.
