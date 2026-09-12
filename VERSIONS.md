# Version strategy

The repo pins Python application dependencies where practical. Azure platform versions and model availability are intentionally not hard-coded beyond safe defaults because Azure service availability varies by region and can change.

Before a production deployment, lock:

- Terraform provider versions via `.terraform.lock.hcl`
- Azure CLI version in the build image or hosted agent baseline
- Helm chart version
- Python base image digest
- container scanner version
- Azure OpenAI model and deployment version

Run `terraform init` once in the intended environment and commit `.terraform.lock.hcl` to the repo.
