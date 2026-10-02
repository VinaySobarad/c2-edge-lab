# Remote state. A backend block cannot use tfvars (HashiCorp).
# Copy config.s3.tfbackend.example → config.s3.tfbackend (gitignored).
# terraform init -backend-config=config.s3.tfbackend
# CI: terraform init -backend=false

terraform {
  backend "s3" {
    bucket       = ""
    key          = ""
    region       = ""
    encrypt      = true
    use_lockfile = true
  }
}
