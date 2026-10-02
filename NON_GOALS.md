# Non-goals — c2-edge-lab

This repository automates **C2 infrastructure** (CloudFront split-origin, S3 decoy, nginx gate, burn). It does **not** ship a C2 framework.

Do not add:

| Out | Why |
|-----|-----|
| Havoc, Sliver, Cobalt Strike, Mythic, Adaptix install | Operator BYO on the private EC2 |
| Implants, stagers, payload generation | Malware development |
| Gophish, Evilginx, credential harvesting | Ethics / resume risk |
| Inbound SSH (port 22) | Session Manager only |
| Domain fronting as a feature | Dead / blocked on CloudFront HTTPS |
| Lambda Function URL as public C2 | Different product; defender SCPs |
| Cloudflare Zero Trust Terraform | Documented as v2, not this repo |
| wget-cloned vendor websites | Legal risk; ship generic decoy HTML |
| Packer fleet, multi-cloud mesh | Out of v1 |
| Claiming “domain in → full engagement” | Teamserver stays yours |

Authorized lab use only. You own the AWS account and the domain.
