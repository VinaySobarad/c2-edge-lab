# Changelog

## 0.10.5 — 2026-10-02

- README verify path uses `CLOUDFRONT_URL`, `PUBLIC_EC2_IP`, and `TEAMSERVER_IP` from Terraform outputs. Live hostnames, EIPs, and capture dates are not in git.

## 0.10.4 — 2026-10-02

- README live proof: curl commands and captured CloudFront responses from the applied stack (S3 decoy vs nginx gate vs EIP timeout).
- State bucket name moved out of git (`terraform/config.s3.tfbackend`, gitignored). HashiCorp partial backend — not tfvars.
- `.gitignore` matches HashiCorp’s Terraform template (`*.tfvars`, overrides, crash logs, plan files), plus `*.tfbackend`.

## 0.10.3 — 2026-10-01

- `make lab-verify` takes User-Agent and echo body from Terraform (policy YAML / locals), not CLI defaults.
- `lab verify --path`, `--user-agent`, and `--expect-proxy-body` are required so live checks cannot silently use `/cdn/` + LabCallback.
- Teamserver lib dir and echo body are locals, same as `pull_root`.

## 0.10.2 — 2026-10-01

- Callback/probe URLs and `make c2-push` paths come from Terraform locals, not hardcoded `/cdn/` `/lh/` `/opt/c2`.
- Teamserver user-data is gzipped (16 KiB cap). Echo HEAD length matches the body. nginx maps go in `conf.d` (http context).
- CloudFront path patterns must end in `/*`.

## 0.10.1 — 2026-10-01

- Copy-in actually works on the private box: teamserver SG egress to the S3 prefix list (gateway endpoints are not VPC CIDRs).
- Staged binaries are not on the decoy URL: CloudFront OAC is keyed to decoy objects; `stage/*` is denied.
- Teamserver IAM is separate from the redirector. `s3_pull` only accepts `stage/<filename>` into `/opt/c2`.
- `make c2-push` validates DEST, uses JSON SSM parameters, and waits for the command.

## 0.10.0 — 2026-10-01

- Second CloudFront distribution (long-haul hostname, `/lh/*`). Short-haul stays `/cdn/*` on `edge`.
- Copy-in: S3 gateway on the private route table, IAM `stage/*`, stdlib `s3_pull.py`, `make c2-push FILE=`.
- `make burn-hostname` prints `-replace=aws_cloudfront_distribution.edge` and refuses to apply. Long-haul stays.
- SSM `AWS-StartPortForwardingSession` copy-paste for 50050 / 31337 (outputs + byo-c2).
- Thicker decoy (`app.css` / `app.js` / `favicon.svg`) and [docs/categorization.md](docs/categorization.md).
- Default implants still need header + UA + path. Gate is not disabled.

## 0.9.1 — 2026-10-01

- BYO C2 + two-haul notes: ports, CloudFront 443 vs bind 8080, SSM for operator GUI, why a second path on the same hostname is not long-haul (`docs/byo-c2.md`).

## 0.9.0 — 2026-10-01

- Human docs: `docs/adopt.md`, `docs/architecture.md`, `docs/detection.md`, `docs/compare.md`. README points operators at adopt.

## 0.8.0 — 2026-10-01

- Redirector burn is identity burn: `-replace=aws_instance.redirector` and `-replace=aws_eip.redirector`. CloudFront origin follows the new EIP. S3 and the distribution hostname stay.

## 0.7.0 — 2026-10-01

- Burn contract: `make burn-redirector` prints `-replace=aws_instance.redirector` and refuses to apply. EIP is a separate allocation (association, not `instance =` on the EIP). CloudFront origin stays the EIP.

## 0.6.0 — 2026-10-01

- `lab verify` four-check split-origin probe. CI uses in-process mocks; `make lab-verify` is live-only after apply. README shows a green vs red example.

## 0.5.3 — 2026-10-01

- Optional custom domain: empty `domain_name` + `hosted_zone_id` uses the CloudFront default hostname (no ACM, no Route 53). Set both for an alias. `lab verify --domain` vs `--base-url`.

## 0.5.2 — 2026-10-01

- Operator knobs (ACM region, CIDRs, instance/volume, viewer TLS, nginx placeholders) live in `lab.tfvars.example`.
- Plan-time checks: subnets fully inside the VPC and non-overlapping; policy YAML header/port match tfvars; `make conf` placeholders exist in the committed nginx file.
- Redirector apt install retries; EIP waits for the internet gateway.

## 0.5.1 — 2026-10-01

- CloudFront managed policies looked up by name (not UUIDs). The old AllViewer UUID was actually CORS-CustomOrigin and would have dropped `X-Lab-Token`.
- IAM SSM policy and decoy bucket policy via data sources. Default VPC security group closed.

## 0.5.0 — 2026-10-01

- CloudFront second origin: EIP HTTP :80, ordered `/cdn/*`, CachingDisabled + AllViewer, 60s origin timeout. Default `/*` stays on private S3.

## 0.4.1 — 2026-10-01

- Terraform remote state: S3 partial backend; bucket/key in gitignored `config.s3.tfbackend` (not tfvars — Terraform forbids interpolating variables into `backend {}`).

## 0.4.0 — 2026-10-01

- Two EC2s (redirector + private teamserver echo), EIP, SSM instance profile, IMDSv2, no SSH keys.
- nginx conf is rendered by the policy CLI; Terraform only substitutes backend IP and header token.

## 0.3.0 — 2026-10-01

- Terraform step 3: VPC, public/private subnets, no NAT, SSM interface endpoints, SGs with no SSH.
- Tests assert Terraform never opens port 22.

## 0.2.0 — 2026-10-01

- Terraform step 2: private S3 decoy, OAC, ACM (us-east-1), Route 53 alias, CloudFront HTTPS.
- CI: `terraform fmt` + `validate`.

## 0.1.0 — 2026-10-01

- Policy engine: `lab policy validate`, `render-nginx`, `test`.
- In-process gate fixtures and `nginx -t` in CI (standalone conf).
- No AWS resources yet (BUILD.md step 1).
