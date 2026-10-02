# c2-edge-lab — product specification

**Status:** Step 4 implemented (two EC2s + EIP + SSM IAM). **Do not apply until asked.** **Build against [BUILD.md](BUILD.md).**  
**Purpose:** capability inventory. **Build against [BUILD.md](BUILD.md)** — if this file and BUILD disagree, BUILD wins.  
**Audience:** you, future contributors, resume/interview prep.

**One-line pitch:** Automated **C2 infrastructure** lab on AWS: two CloudFront hostnames, **S3 decoy (OAC)** for humans, **policy-driven nginx** for callback paths, **private BYO teamserver**, **SSM (no port 22)**, **verify + EIP burn + hostname burn**. Does **not** install C2 frameworks, implants, or phishing kits.

---

## 1. Final research conclusion (deep pass)

### 1.1 What the field already solves

| Source | What it does well |
|--------|-------------------|
| [Lorenzo Meacci — AWS C2 infra](https://lorenzomeacci.com/creating-a-c2-infrastructure-on-aws) | Manual Route53, EC2 Apache, SSH `-R`, optional Havoc; teaches the **tunnel + redirector** pattern |
| [Trizna — C2 traffic redirectors](https://ditrizna.medium.com/design-and-setup-of-c2-traffic-redirectors-ec3c11bd227d) | nginx proxy, Let’s Encrypt, **UA + IP filters**, decoy pages, **short/long haul** concepts, burn redirectors |
| [bluescreenofjeff — mod_rewrite](https://bluescreenofjeff.com/2016-06-28-cobalt-strike-http-c2-redirectors-with-apache-mod_rewrite/) | URI + UA gating; decoy for non-matching traffic |
| [Optiv — CloudFront + redirector](https://www.optiv.com/insights/discover/blog/redirectors-red-teamers-introduction) | CloudFront in front of Apache; **managed prefix list** on origin SG so only CloudFront hits the redirector |
| [Grey Corner (2025) — cloud C2 summary](https://thegreycorner.com/2025/10/02/abusing-cloud-services-for-c2) | **High-reputation redirectors** vs **domain fronting** (largely dead for HTTPS implants); AWS service catalog |
| [redStack](https://github.com/BaddKharma/redStack) | Full AWS lab: Apache redirector (**scanner block**, **header**, **URI prefixes**), multiple C2 frameworks, VPC peering |
| [C2structor](https://github.com/optionalCTF/C2structor) | CloudFront edge + Caddy + optional Havoc; Route53 in `tfvars` |
| [Red-Terroir](https://github.com/b3n-j4m1n/Red-Terroir) | HTTP/DNS/phishing/mail channels; **destroy & rebuild** redirectors |
| [WolfPack](https://github.com/RoseSecurity/WolfPack) | **Packer AMI** + Apache `.htaccess` at scale |
| [Malleable-Redirector](https://github.com/inthecyber-group/Malleable-Redirector) | Cobalt profile → nginx/apache/caddy; strict/lax policy |
| [cs2modrewrite](https://github.com/threatexpress/cs2modrewrite/) / [Tyche](https://github.com/Whispergate/Tyche) | Profile → rewrite rules |
| [cgomezsec — CF Worker + ZT](https://cgomezsec.com/blog/securing-c2-for-rt-operations-using-cloudflare) | Worker header gate + **cloudflared** tunnels; honeypot for invalid traffic |
| [RastaMouse / mantvydas — Terraform RT infra](https://rastamouse.me/infrastructure-as-code-terraform-ansible/) | Terraform + Ansible; burn redirectors; separate smtp/payload/C2 roles |

### 1.2 Confirmed gaps (where we add value)

1. **Split-origin CloudFront in one lab product:** default behavior → **S3 decoy (OAC, private bucket)**; selected paths → **EC2 nginx** gated origin—not marketed as a single cohesive OSS repo alongside policy CI.
2. **Framework-agnostic `redirector.policy.yaml`** with **validate / render / test** (pst-gate-style discipline), not Cobalt-only generators.
3. **Lab verify + burn contract** automated in CI (`nginx -t`, fixture HTTP checks), not just README prose.
4. **Defender pack** in the same repository (CloudFront/VPC/nginx log fields, detection ideas)—rare next to attack-only repos.
5. **Absorbs prior resume work:** static site on S3 + CloudFront (OAC, HTTPS, least-privilege) as the **decoy layer**, not a separate GitBook-only story.

### 1.3 What research says **not** to center

| Topic | Why exclude or demote |
|-------|------------------------|
| **Classic HTTPS domain fronting** | [AWS CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html) enforces SNI/Host alignment; [Grey Corner](https://thegreycorner.com/2025/10/02/abusing-cloud-services-for-c2) notes implants rarely support required SNI tricks |
| **Lambda Function URL public C2** | [Qualys HazyBeacon](https://blog.qualys.com/qualys-insights/2026/06/02/hazybeacon-aws-lambda-function-url-command-control-abuse)—defenders SCP-block; different product class |
| **Full C2 framework install** | [redStack](https://github.com/BaddKharma/redStack) / [C2structor](https://github.com/optionalCTF/C2structor) already own this |
| **“Domain in → entire engagement automated”** | Teamserver, listeners, payloads remain **operator steps** (honest UX) |

---

## 2. Our unique combination (borrow + own)

**We borrow (with credit in README):**

- Redirector goals from [Trizna](https://ditrizna.medium.com/design-and-setup-of-c2-traffic-redirectors-ec3c11bd227d): hide backend, mimic legit traffic, filter non-implant traffic, survive burn.
- Segregation / short vs long haul from [Bluescreen](https://bluescreenofjeff.com/2017-12-05-designing-effective-covert-red-team-attack-infrastructure/) and [Cobalt Strike](https://www.cobaltstrike.com/blog/infrastructure-for-ongoing-red-team-operations/).
- CloudFront origin protection from [Optiv](https://www.optiv.com/insights/discover/blog/redirectors-red-teamers-introduction).
- Optional profile import from [Malleable-Redirector](https://github.com/inthecyber-group/Malleable-Redirector) (integrate, don’t reimplement CS parser).
- BYO teamserver from [Lorenzo](https://lorenzomeacci.com/creating-a-c2-infrastructure-on-aws) (his SSH `-R` is **alternate**, not v1).
- SSM-instead-of-SSH from [Red-Formation](https://github.com/scottctaylor12/Red-Formation) (borrowed, not unique).

**We own (differentiators):**

1. **Split-origin edge lab** — believable **S3 decoy (OAC)** + **gated nginx origin** under one CloudFront hostname.
2. **Policy-as-code engine** — `redirector.policy.yaml` → nginx; `lab policy validate | render-nginx | test`; invalid policy fails CI.
3. **Burn the redirector identity** — new EC2 **and new EIP**; CloudFront origin follows. S3 + the CF hostname stay.
4. **`NON_GOALS.md`** + thin `docs/detection.md` (what logs exist — not a Sigma product).

---

## 3. Architecture options

### 3.1 Primary (recommended): one domain, split origins

```text
Internet
   │
   ▼
Route 53 ──► ACM cert
   │
   ▼
CloudFront (custom domain, HTTPS)
   ├── default /*          ──► S3 origin (decoy, OAC, private bucket)
   └── ordered /cdn/*      ──► Redirector EC2 :80 (EIP; SG = CloudFront prefix list)
                                    nginx from policy YAML (header + URI + UA)
                                    deny → local decoy HTML
                                    allow → private teamserver EC2 :8080
                                    SSM on both hosts — NO port 22
```

### 3.2 Alternative (simpler ops): two hostnames

| Hostname | Backend |
|----------|---------|
| `www.example.com` | CloudFront → S3 decoy only |
| `cdn.example.com` (or `api.`) | EC2 nginx redirector (Lorenzo-style) |

Document both; implement **3.1** in v1. Use **3.2 only** if BUILD.md step 5 (path split) fails dogfood.

### 3.3 Optional pattern (documented, not v1): CloudFront → redirector only

Per [Optiv](https://www.optiv.com/insights/discover/blog/redirectors-red-teamers-introduction): implant calls **CloudFront URL**; origin is Apache/nginx on EC2; SG allows **only** `com.amazonaws.global.cloudfront.origin-facing` prefix list. Can complement 3.1 (extra cache behavior) or be ADR comparison.

### 3.4 Phase 2 edge (optional module): Cloudflare

Per [cgomezsec](https://cgomezsec.com/blog/securing-c2-for-rt-operations-using-cloudflare): Worker header check → proxy to tunnel hostname; **cloudflared** on operator/EC2; service auth tokens. Semi-automated; separate `docs/cloudflare-edge.md` + optional Wrangler subtree—not v1 Terraform monolith.

---

## 4. Capability inventory (everything discussed in planning)

Use checkboxes when implementing. **Phase** column: `v1` | `v1.5` | `v2` | `doc-only`.

### 4.1 Infrastructure (Terraform / AWS)

| # | Capability | Phase | Notes |
|---|------------|-------|-------|
| I1 | Route 53 DNS records (A/AAAA alias to CloudFront) | v1 | Bring your own hosted zone + domain |
| I2 | ACM certificate (DNS validation) | v1 | HTTPS viewers |
| I3 | S3 bucket for decoy assets (no public ACL) | v1 | Replaces standalone static-site project |
| I4 | CloudFront **Origin Access Control (OAC)** for S3 | v1 | Only CloudFront reads bucket; least-privilege bucket policy |
| I5 | CloudFront distribution with **multiple origins** | v1 | S3 + EC2 custom origin |
| I6 | **Ordered cache behaviors** (path → nginx origin) | v1 | e.g. `/cdn/*`, `/api/v1/*` configurable |
| I7 | Default cache behavior → S3 decoy | v1 | GET/HEAD for static site |
| I8 | Viewer protocol **redirect-to-https** | v1 | Edge security |
| I9 | EC2 redirector (small instance, e.g. t3.micro) | v1 | nginx |
| I10 | Redirector SG: **:80 from CloudFront managed prefix list only** | v1 | Not world-open. Not 443 on EC2. [Optiv](https://www.optiv.com/insights/discover/blog/redirectors-red-teamers-introduction) |
| I11 | **No inbound SSH (22)** on either instance | v1 | Session Manager instead |
| I12 | **IMDSv2** required on EC2 | v1 | Hardening |
| I13 | CloudFront prefix list on origin SG | v1 | Same as I10 — not a later phase |
| I14 | VPC: public subnet (redirector + EIP) + **private subnet (teamserver)** | v1 | Two EC2s |
| I15 | **Elastic IP** on redirector | v1 | Required for burn; CloudFront origin = EIP |
| I16 | TLS **only at CloudFront**; origin **HTTP :80** | v1 | No Certbot on EC2 |
| I17 | `terraform output`: decoy URL, callback path, **`aws ssm start-session` one-liners** | v1 | No SSH one-liner |
| I18 | `terraform output`: connect URL for listener (operator docs) | v1 | Not auto-configuring C2 |
| I19 | **Targeted destroy/replace** redirector (`-replace` / `-target`) | v1 | Burn workflow; EIP resource stays |
| I20 | Redirector **count = N** (fleet) | v2 | [Red-Terroir](https://github.com/b3n-j4m1n/Red-Terroir), [WolfPack](https://github.com/RoseSecurity/WolfPack) |
| I21 | **Packer golden AMI** for redirector | v2 | WolfPack-style |
| I22 | EventBridge **auto-stop** / budget alarm | v1.5 | Cost guard |
| I23 | VPC Flow Logs (optional) | v1.5 | Defender + your observability story |
| I24 | CloudFront access logging to S3 (optional) | v1.5 | Input for detection notes |
| I25 | IAM instance profile `AmazonSSMManagedInstanceCore` on **both** EC2s | v1 | |
| I26 | VPC interface endpoints `ssm` + `ssmmessages` + `ec2messages` | v1 | Private teamserver login without NAT |
| I27 | NAT gateway | **out of v1** | Optional flag later for apt/C2 download on private host |

### 4.2 Decoy layer (S3 + content)

| # | Capability | Phase | Notes |
|---|------------|-------|-------|
| D1 | Ship **generic corporate/marketing** HTML template(s) in repo | v1 | No cloned vendor sites ([Trizna wget](https://ditrizna.medium.com/design-and-setup-of-c2-traffic-redirectors-ec3c11bd227d) = legal/ethical risk) |
| D2 | Upload/sync decoy assets via Terraform (`aws_s3_object` or `terraform apply` hook) | v1 | |
| D3 | Fake login **UI only** (no credential harvesting) — optional static page | v1.5 | Resume-safe |
| D4 | `robots.txt`, favicon, plausible JS/CSS | v1 | Categorization / realism ([Trizna](https://ditrizna.medium.com/design-and-setup-of-c2-traffic-redirectors-ec3c11bd227d) discusses reputation) |
| D5 | Document **domain categorization** (manual checklist, not automated scraping) | doc-only | PAN/Symantec/Checkpoint URLs in docs |

### 4.3 Redirector policy engine (Python CLI: `lab`)

| # | Capability | Phase | Notes |
|---|------------|-------|-------|
| P1 | `redirector.policy.yaml` schema (versioned) | v1 | Single source of truth |
| P2 | **Custom header** name + secret (gate valid callbacks) | v1 | [redStack](https://mintlify.wiki/BaddKharma/redStack/introduction), [cgomezsec](https://cgomezsec.com/blog/securing-c2-for-rt-operations-using-cloudflare) |
| P3 | **URI path prefix(es)** for proxy allow | v1 | CDN-like paths e.g. `/cdn/media/stream` |
| P4 | **User-Agent allowlist** (exact or regex) | v1 | [bluescreenofjeff](https://bluescreenofjeff.com/2016-06-28-cobalt-strike-http-c2-redirectors-with-apache-mod_rewrite/) |
| P5 | Optional **source CIDR allowlist** | v1.5 | [Trizna](https://ditrizna.medium.com/design-and-setup-of-c2-traffic-redirectors-ec3c11bd227d) |
| P6 | **Scanner / noise UA blocklist** (curl, wget, nikto, nmap, masscan, etc.) | v1 | [Hacker Hermanos](https://hackerhermanos.com/posts/traffic-filtering-c2-redirectors/), [redStack redirect.rules](https://mintlify.wiki/BaddKharma/redStack/introduction) |
| P7 | nginx **`return 444`** for known-bad scanners (optional mode) | v1.5 | [Hacker Hermanos](https://hackerhermanos.com/posts/traffic-filtering-c2-redirectors/) |
| P8 | Non-matching traffic → **decoy response** (local static or redirect to S3 path) | v1 | Default deny proxy |
| P9 | Invalid header → decoy / maintenance page (HTTP 200) | v1 | [redStack](https://mintlify.wiki/BaddKharma/redStack/architecture) CloudEdge-style |
| P10 | Optional redirect to **external honeypot URL** for invalid requests | v1.5 | [cgomezsec](https://cgomezsec.com/blog/securing-c2-for-rt-operations-using-cloudflare) |
| P11 | `lab policy validate` | v1 | Fails exit 2 on bad YAML |
| P12 | `lab policy render-nginx` | v1 | Template → `/etc/nginx/...` |
| P13 | `lab policy test` (fixture requests) | v1 | Unit tests |
| P14 | Policy modes: **strict** / **lax** / **lab-open** (disable scanner block) | v1.5 | [Malleable-Redirector](https://github.com/inthecyber-group/Malleable-Redirector); HTB/VL toggle like [redStack](https://mintlify.wiki/BaddKharma/redStack/reference/variables) |
| P15 | Auto-generate header secret if empty in tfvars | v1 | [redStack `c2_header_value`](https://mintlify.wiki/BaddKharma/redStack/setup/terraform-variables) |
| P16 | **Import** Sliver `http-c2.json` headers into policy | v1.5 | Narrow import |
| P17 | **Optional shell-out** to Malleable-Redirector for Cobalt `.profile` | v1.5 | Don’t vendor their code; document integration |
| P18 | User-data installs nginx and writes **CLI-rendered** conf (Terraform only substitutes host + header) | v1 | No handwritten maps in HCL |

### 4.4 Operator / BYO teamserver (infra is automated; frameworks are not)

| # | Capability | Phase | Notes |
|---|------------|-------|-------|
| O1 | Document **SSM** login + **SSM port-forward** for C2 UIs | v1 | [Red-Formation](https://github.com/scottctaylor12/Red-Formation). SSH `-R` is **alternate / doc-only**, not v1 infra |
| O2 | nginx `proxy_pass` to **teamserver private IP:8080** (echo stub in v1) | v1 | Tunnel-to-localhost is not the v1 path |
| O3 | **No install** of Havoc/Sliver/Cobalt/Mythic in repo | v1 | NON_GOAL |
| O4 | **No payload / beacon generation** in repo | v1 | NON_GOAL |
| O5 | Listener “connect address” = CloudFront domain or path URL (docs only) | v1 | |

### 4.5 Short-haul / long-haul (segmentation)

| # | Capability | Phase | Notes |
|---|------------|-------|-------|
| H1 | **Short-haul** channel: `edge` distribution + `/cdn/*` | shipped | Frequent callbacks |
| H2 | **Long-haul** channel: second distribution + `/lh/*` | shipped | Rare callbacks; different hostname |
| H3 | Documentation: do not point all persistence at long-haul | doc-only | [Cobalt Strike](https://www.cobaltstrike.com/blog/infrastructure-for-ongoing-red-team-operations/) |
| H4 | Same BYO teamserver vs separate backends (operator choice) | doc-only | Still one private box |

### 4.6 Lab workflows (Makefile or scripts)

| # | Capability | Phase | Notes |
|---|------------|-------|-------|
| W1 | `make lab-up` / `terraform apply` with example `lab.tfvars.example` | v1 | |
| W2 | `make lab-verify` / `lab verify` — decoy 200, bad header decoy, good header proxied (mock backend in CI) | v1 | |
| W3 | `make burn-redirector` — replace redirector **instance + EIP**; CloudFront origin follows | v1 | |
| W4 | `make lab-down` / full destroy | v1 | Ephemeral lab |
| W5 | Example **red vs green** CI or doc (failed verify vs pass) | v1.5 | pst-gate-style proof |

### 4.7 CI / quality (GitHub Actions)

| # | Capability | Phase | Notes |
|---|------------|-------|-------|
| C1 | `terraform fmt` / `validate` | v1 | |
| C2 | `tflint` (optional) | v1.5 | |
| C3 | Render nginx from fixture policy + `nginx -t` | v1 | |
| C4 | `pytest` for policy engine | v1 | |
| C5 | `ruff` on Python | v1 | |
| C6 | No secrets in repo; example tfvars only | v1 | |

### 4.8 Detection notes (thin — not a product)

| # | Capability | Phase | Notes |
|---|------------|-------|-------|
| B1 | **One file** `docs/detection.md` — what blue team sees | v1 | Not a pack |
| B2 | Mention CF headers `via`, `x-amz-cf-pop`, `x-amz-cf-id` | v1 | Inside that file |
| B3 | Origin-facing prefix list | v1 | Same file |
| B4 | nginx access log fields for gated paths | v1 | Same file |
| B5 | Sample **synthetic log lines** | v1.5 | |
| B6 | Short detection ideas | v1 | Same file, not a Sigma repo |
| B7 | Layered diagram | v1 | Lives in `docs/architecture.md` |

### 4.9 Documentation / ADRs

| # | Capability | Phase | Notes |
|---|------------|-------|-------|
| R1 | `README.md` — what / why / authorized lab only / setup | v1 | |
| R2 | `docs/architecture.md` — diagrams 3.1 and 3.2 | v1 | |
| R3 | `docs/adopt.md` — inputs, outputs, first apply | v1 | |
| R4 | `docs/adr-001-aws-split-origin-vs-cloudflare-worker.md` | v1.5 | [cgomezsec](https://cgomezsec.com/blog/securing-c2-for-rt-operations-using-cloudflare) |
| R5 | `docs/adr-002-aws-split-origin-vs-lambda-relay.md` | doc-only | [brewcoffee.io Lambda](https://brewcoffee.io/blog/aws-lambda-c2-redirector/), [Qualys](https://blog.qualys.com/qualys-insights/2026/06/02/hazybeacon-aws-lambda-function-url-command-control-abuse) |
| R6 | Comparison table: vs Lorenzo, C2structor, redStack, WolfPack | v1 | Honest credits |
| R7 | `NON_GOALS.md` | v1 | |
| R8 | `CHANGELOG.md` when code exists | v1 | |

### 4.10 Resume / Harness framing (not code)

| # | Capability | Phase | Notes |
|---|------------|-------|-------|
| X1 | Resume bullet: **automated C2 infrastructure** — Terraform, CloudFront split-origin, S3 OAC decoy, policy nginx | doc-only | pst-gate stays hero; this is project #3 |
| X2 | GitHub README may lead with **automated C2 infrastructure**; still say BYO teamserver | doc-only | Honest: we automate the edge, not Havoc/Sliver install |
| X3 | Replaces standalone S3/CloudFront write-up **only after** repo proves 3.1 | doc-only | |

---

## 5. Explicit non-goals (do NOT build)

These were considered in planning and **rejected** for this repository.

| Non-goal | Reason |
|----------|--------|
| Install/configure **Havoc, Sliver, Cobalt Strike, Mythic, Adaptix** | [redStack](https://github.com/BaddKharma/redStack), [C2structor](https://github.com/optionalCTF/C2structor) |
| **Gophish, Evilginx2**, credential phishing | Scope, ethics, resume risk |
| **[SpotifyC2](https://github.com/NirvanaOn/SpotifyC2)**-style channels | Unrelated architecture |
| **Multi-cloud relays** (Azure/GCP/Lambda mesh) | [RedTeamTerra](https://github.com/Allevon412/RedTeamTerra)—unfocused |
| **Domain fronting** as marketed feature | [Grey Corner](https://thegreycorner.com/2025/10/02/abusing-cloud-services-for-c2), [AWS docs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html) |
| **Lambda Function URL** public C2 relay | Defender SCPs; malware association |
| **Full Cloudflare Zero Trust** one-click Terraform | [cgomezsec](https://cgomezsec.com/blog/securing-c2-for-rt-operations-using-cloudflare)—semi-manual v2 |
| **Auto-purchase domains** in Terraform | Slow, registrar APIs, not core value |
| **wget clone** of real vendor sites | [Trizna](https://ditrizna.medium.com/design-and-setup-of-c2-traffic-redirectors-ec3c11bd227d)—legal/ethical risk |
| **AV/EDR bypass**, implants, stagers in repo | Malware dev belongs in separate research |
| **AI-generated Terraform** as feature | [GuidePoint](https://www.guidepointsecurity.com/blog/automating-cloudfront-c2-with-ai/)—gimmick |
| **Guacamole + Windows victim + AD lab** | redStack scope |
| **SMTP / phishing redirector channel** | [mantvydas](https://github.com/mantvydasb/redteaming-tactics-and-techniques/blob/master/offensive-security/red-team-infrastructure/automating-red-team-infrastructure-with-terraform.md) separate concern |
| **DNS C2 redirector channel** | Red-Terroir scope |
| **GeoIP / time-of-day nginx** (initially) | v2 nice-to-have; cron complexity |
| Claim **“one domain → full engagement ready”** | Misleading; teamserver stays BYO |
| **Inbound SSH (port 22)** | SSM instead; [Red-Formation](https://github.com/scottctaylor12/Red-Formation) already showed this |

---

## 6. Configuration inputs (planned `lab.tfvars`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `domain_name` | yes | Primary FQDN |
| `hosted_zone_id` | yes | Route 53 |
| `callback_path_patterns` | yes | CloudFront → nginx paths (e.g. `/cdn/*`) |
| `policy_file` | yes | Header, UA, paths (`policy/redirector.policy.yaml`) |
| `decoy_template` | no | Which static template |
| `redirector_instance_type` | no | default `t3.micro` |
| `enable_scanner_blocking` | no | default true; false for HTB-style labs |
| `short_haul` / `long_haul` blocks | no | v1.5 |
| `aws_region` | no | default e.g. `us-east-1` |

**Not in v1:** `operator_cidr`, `ssh_key_name`, `snyk_token`, C2 framework pins, implant URIs. Header **value** is generated (`random_password`) unless set locally — never commit it.

---

## 7. Phase delivery plan

| Phase | Goal | Ship when |
|-------|------|-----------|
| **v1** | Follow **[BUILD.md](BUILD.md) steps 1–8**. Infra: I1–I19, I25–I26. Decoy D1–D2, D4. Policy P1–P4, P6, P8–P9, P11–P13, P15, P18. Operator O1–O5 (SSM). Workflows W1–W4. CI C1+C3–C6. Docs R1–R3, R6–R8 + one `docs/detection.md` | First public repo after AWS dogfood of step 5 |
| **v1.5** | I22–I24, D3, P5/P7/P10/P14–P17, H1–H2, W5, B5, R4, optional NAT flag | After v1 green CI + one real apply |
| **v2** | I20–I21, Cloudflare Worker, GeoIP, VPC origin | Only if v1.5 stable |

---

## 8. Success criteria (how we know it worked)

1. **`terraform apply`** with example tfvars creates decoy site + gated path without manual Apache editing.
2. **`lab verify`** passes in CI (with mock backend).
3. **`make burn-redirector`** replaces EC2 **and EIP**; decoy URL (CloudFront hostname) still serves S3 content.
4. README comparison table credits prior art; **`NON_GOALS.md`** present.
5. A security engineer unfamiliar with the repo understands **what it does in 5 minutes** without reading Cobalt Strike docs.

---

## 9. Decisions (locked — see BUILD.md)

| # | Decision | Lock |
|---|----------|------|
| 1 | Architecture | **3.1** one domain, split origin. 3.2 only if step 5 dogfood fails |
| 2 | Origin TLS | **HTTP-only** behind CloudFront |
| 3 | Repo name | **`c2-edge-lab`** |
| 4 | Proxy | **nginx** (`map` + named locations; no `if` + `proxy_pass`) |
| 5 | Admin | **SSM, no port 22** |
| 6 | Burn | **New EIP**; replace redirector instance; CloudFront origin follows |
| 7 | Detection | **One markdown file** |

---

## 10. Reference index

- Lorenzo: https://lorenzomeacci.com/creating-a-c2-infrastructure-on-aws  
- Trizna: https://ditrizna.medium.com/design-and-setup-of-c2-traffic-redirectors-ec3c11bd227d  
- Optiv CloudFront: https://www.optiv.com/insights/discover/blog/redirectors-red-teamers-introduction  
- Grey Corner 2025: https://thegreycorner.com/2025/10/02/abusing-cloud-services-for-c2  
- cgomezsec CF Worker: https://cgomezsec.com/blog/securing-c2-for-rt-operations-using-cloudflare  
- redStack: https://github.com/BaddKharma/redStack  
- C2structor: https://github.com/optionalCTF/C2structor  
- Red-Terroir: https://github.com/b3n-j4m1n/Red-Terroir  
- WolfPack: https://github.com/RoseSecurity/WolfPack  
- Malleable-Redirector: https://github.com/inthecyber-group/Malleable-Redirector  
- Bluescreen segregation: https://bluescreenofjeff.com/2017-12-05-designing-effective-covert-red-team-attack-infrastructure/  
- Cobalt Strike hauls: https://www.cobaltstrike.com/blog/infrastructure-for-ongoing-red-team-operations/  
- Hacker Hermanos filtering: https://hackerhermanos.com/posts/traffic-filtering-c2-redirectors/  
- 0xda nginx RT: https://0xda.de/blog/2020/02/nginx-for-red-teams/  
- Prior resume S3/CloudFront write-up: GitBook Terraform static site (to be superseded by this repo when built)

---

*Last updated: aligned to ANALYSIS freeze + BUILD.md — still no implementation.*
