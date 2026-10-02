# Adopt — stand up the lab

Authorized use only. You own the AWS account. Do not point this at systems you do not own.

This file is the operator path. You do not need Cobalt Strike docs. This repo does **not** install a C2 framework. v1 ships a stdlib echo on the private EC2 so `lab verify` can prove the gate. To put your own C2 on that box, see [byo-c2.md](byo-c2.md) (ports, gate, copy-in, short-haul vs long-haul).

## What you get

Two CloudFront hostnames (two distributions, still two EC2s):

- Short-haul: `/*` → private S3 decoy (OAC); `/cdn/*` → nginx
- Long-haul: second `dxxxx.cloudfront.net`; `/*` → same S3; `/lh/*` → same nginx
- nginx proxies only if policy matches (header + allowed User-Agent)
- Private teamserver EC2 (no public IP, no NAT). Copy a binary with `make c2-push`
- Login is **SSM Session Manager**. No port 22

## Inputs

Copy `lab.tfvars.example` → `lab.tfvars` (gitignored). Copy `terraform/config.s3.tfbackend.example` → `terraform/config.s3.tfbackend` (gitignored) and put your state bucket there. Terraform **cannot** read the backend from tfvars.

| Variable | Required? | Notes |
|----------|-----------|--------|
| `domain_name` + `hosted_zone_id` | No | Leave both empty → `https://dxxxx.cloudfront.net`. Set **both** for a custom hostname (ACM in `us-east-1` + Route 53 alias) |
| `aws_region` | Yes | Default `us-east-1` |
| `acm_region` | Yes | Must stay `us-east-1` for CloudFront certs |
| VPC CIDRs | Yes | Defaults in the example. Subnets must sit inside the VPC |
| `instance_type` / volume | Yes | Defaults `t3.micro` / `gp3` / 8 GiB |
| `callback_path_patterns` | Yes | Default `["/cdn/*"]` — short-haul ordered behavior |
| `longhaul_path_patterns` | Yes | Default `["/lh/*"]` — second CloudFront hostname |
| `callback_header_name` | Yes | Must match `policy/redirector.policy.yaml` |
| `nginx_*_placeholder` | Yes | Must match `make conf` (`192.0.2.1` / `PLACEHOLDERHEADER`) |

**You also need:** AWS credentials that can create VPC/EC2/CloudFront/S3 (and ACM/Route 53 if using a domain), the Session Manager plugin, and an existing S3 bucket for Terraform state (name goes in `terraform/config.s3.tfbackend`, not in git).

You do **not** need a Cloudflare account or API token. This is **Amazon CloudFront**.

## First apply

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make test

cp lab.tfvars.example lab.tfvars
cp terraform/config.s3.tfbackend.example terraform/config.s3.tfbackend
# set the state bucket in terraform/config.s3.tfbackend
# optional: set domain_name + hosted_zone_id

make tf-validate

# You run apply. Make will refuse.
cd terraform
terraform init -backend-config=config.s3.tfbackend
terraform apply -var-file=../lab.tfvars
cd ..
```

`make decoy-up` / `make lab-up` / `make burn-redirector` print the command and exit. They do not apply.

## After apply

```bash
terraform -chdir=terraform output decoy_url
terraform -chdir=terraform output longhaul_url
terraform -chdir=terraform output ssm_redirector
terraform -chdir=terraform output ssm_teamserver
terraform -chdir=terraform output ssm_cs_port_forward
terraform -chdir=terraform output ssm_sliver_port_forward
# sensitive:
terraform -chdir=terraform output -raw lab_header_value

make lab-verify
make lab-verify-longhaul
```

Expect decoy HTML on `/` of **both** hostnames. Expect `terraform output echo_body` on `callback_probe_path` (short) and `longhaul_probe_path` (long) only with the header **and** `callback_user_agent`.

Login (no SSH):

```bash
aws ssm start-session --target "$(terraform -chdir=terraform output -raw redirector_instance_id)"
```

Port-forward copy-paste is in [byo-c2.md](byo-c2.md). Categorize the decoy with [categorization.md](categorization.md).

## Burn (identity)

New redirector VM **and** new EIP. CloudFront origin follows the new IP. The CloudFront hostname (what a callback uses) stays.

```bash
make burn-redirector
# then you run:
terraform -chdir=terraform apply -var-file=../lab.tfvars \
  -replace=aws_instance.redirector \
  -replace=aws_eip.redirector
```

If the **short-haul CloudFront hostname** is blocked, rotating the EIP does nothing. That is hostname burn:

```bash
make burn-hostname
# then you run:
terraform -chdir=terraform apply -var-file=../lab.tfvars \
  -replace=aws_cloudfront_distribution.edge
```

Long-haul `dxxxx` is not replaced.

## Destroy

```bash
terraform -chdir=terraform destroy -var-file=../lab.tfvars
```

`make decoy-down` refuses. You run destroy yourself.
