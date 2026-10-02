# Low-level analysis — before any code

**Status:** research only. Do not implement until this file is accepted.  
**Companion:** [SPEC.md](SPEC.md) stays the capability inventory. This file is the **honest map**: what we copy, what is actually ours, what is broken in the spec, and the build order that avoids the first-attempt failures.

---

## 0. What we are actually building (freeze)

One sentence:

> **Automated C2 infrastructure lab (`c2-edge-lab`):** one domain on CloudFront. Humans hit an **S3 decoy (OAC)**. Callback paths hit **nginx on a redirector**. Nginx only proxies if policy matches (header + path + UA). Backend is a **private EC2 you install C2 on**. Admin is **Session Manager — no port 22 on the internet.** Burn the redirector; keep the decoy.

That is **Tier 1 + thin Tier 3 docs** from the earlier research notes. Not redStack. Not Lorenzo clone. Not Cloudflare. Not Lambda.

| In v1 | Out of v1 |
|-------|-----------|
| CF multi-origin: S3 decoy + nginx | Installing Havoc/Sliver/Mythic |
| `redirector.policy.yaml` → nginx + CI `nginx -t` | Evilginx / Gophish / SpotifyC2 |
| Two EC2s: redirector (EIP) + private teamserver | Port **22** open to the internet (or at all) |
| **SSM Session Manager** to both boxes | Domain fronting, Function URLs |
| Redirector **:80 only from CloudFront prefix list** | Packer fleet, multi-cloud, CF Worker Terraform |
| `lab verify` + `make burn-redirector` (new EIP; CF origin follows) | Long-haul second domain (v1.5) |
| Thin `docs/detection.md` | “Purple pack” as a product |

**Admin vs implant traffic (easy to mix up):**

| Port / path | Exposed to internet? | Why |
|-------------|----------------------|-----|
| 22 SSH | **No** | Session Manager instead ([AWS](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html), [Red-Formation](https://github.com/scottctaylor12/Red-Formation) already does this for RT labs) |
| Teamserver listen port (e.g. 8443) | **No** | Only redirector SG inside VPC |
| Redirector :80 | **Only CloudFront IPs** | Prefix list — not “the whole internet,” not SSH |
| CloudFront :443 | **Yes** | That **is** the public site + callback URL |

SSM does **not** hide the redirector from CloudFront. It only removes **login** from the internet.

---

## 0.1 Unique thing (one sentence)

**The unique thing:** CloudFront **splits one hostname** — default traffic is a **real private S3 website (OAC)**; only **callback paths** go to **nginx**. Filters live in **policy YAML with tests**. Burn **only** the redirector EC2; **S3 + CloudFront stay**.

That is **not** “we invented redirectors.” Redirectors are crowded. **This packaging** is what we add.

| Piece | Unique? | Who already did it (fresh check, Oct 2026) |
|-------|---------|------------------------------------------|
| nginx/Apache path + UA + decoy on the **same VM** | No | [Trizna](https://ditrizna.medium.com/design-and-setup-of-c2-traffic-redirectors-ec3c11bd227d), [xbz0n](https://xbz0n.sh/blog/c2-redirectors), [scarlet nginx](https://red.tymyrddin.dev/docs/scarlet/iac/redirectors/nginx-redirector) |
| CloudFront **in front of** one redirector origin | No | [Optiv](https://www.optiv.com/insights/discover/blog/redirectors-red-teamers-introduction), [DbgMan 2025](https://0xdbgman.github.io/posts/red-team-infrastructure-the-full-picture/), [RoseSecurity](https://github.com/RoseSecurity/Red-Teaming-TTPs/blob/main/Creative%20C2%20Obfuscation%20-%20CloudFronting%20Through%20Firewalls%20and%20Hiding%20in%20Plain%20PCAP.md) |
| Header + URI gate, decoy HTML on **disk** | No | [redStack](https://mintlify.wiki/BaddKharma/redStack/redirector/overview) |
| Terraform + Havoc + autossh | No | [100 Days of Red Team](https://www.100daysofredteam.com/p/red-team-infrastructure-deploying-a-redirector-via-terraform) |
| Profile → Caddy/nginx file | No | [CaddySmith](https://github.com/IceCubeSandwich/CaddySmith) (new: CS **and Sliver**), [cs2modrewrite](https://github.com/threatexpress/cs2modrewrite/) |
| DO + Caddy + WireGuard | No | [PrimusRedir](https://github.com/Primusinterp/PrimusRedir) |
| S3 + CloudFront | No as **website**; [infrahouse](https://github.com/infrahouse/terraform-aws-http-redirect) is **301 SEO**, not C2 |
| SSM, no SSH | No | [Red-Formation](https://github.com/scottctaylor12/Red-Formation) |
| **CF behaviors: `/*` → S3 OAC, `/cdn/*` → EC2 nginx, private C2, policy CLI, EIP burn** | **Yes as a product** | **Not found** as a published repo/tutorial in this pass |

**New (2025–2026) that we still do not copy:** DbgMan’s multi-CDN + Lambda + Cloudflare chapter; xbz0n’s single-origin CF boto3; CaddySmith (integrate later, don’t rewrite).

---

## 1. Verdict in one page

The **idea is valid**. The **first implementation was not**. SPEC listed capabilities; it did not lock engineering decisions. That is why it looked messy.

| Question | Answer |
|----------|--------|
| Is “domain in → full C2” true? | **No.** Domain is one of several inputs. Teamserver stays BYO. |
| Are we cloning a repo? | **No single repo** does this exact product. Many repos do **pieces**. |
| Is split-origin unique? | **The combination is unique. Each piece is not.** |
| Should we start coding now? | **Not until §7 decisions are locked.** |

**Product we should actually build (narrow):**

> One Terraform apply: **CloudFront** with two origins — **S3 decoy (OAC)** for humans, **nginx redirector EC2** for gated callback paths. Redirector proxies only matching traffic to a **private BYO teamserver EC2**. **No inbound SSH.** Burn replaces the **redirector instance + EIP**, not the decoy. Python CLI owns **policy YAML → nginx**, with tests. No C2 install.

That is SPEC §3.1 + two-EC2 + burn + **SSM**. Everything else is later or docs.

---

## 2. What already exists (steal with credit, do not re-invent)

### 2.1 Capability → source (borrow map)

| Capability we want | Who already did it | How we use it |
|--------------------|--------------------|----------------|
| Hide teamserver; proxy only implant-like traffic; decoy everyone else | [Trizna](https://ditrizna.medium.com/design-and-setup-of-c2-traffic-redirectors-ec3c11bd227d), [bluescreenofjeff](https://bluescreenofjeff.com/2016-06-28-cobalt-strike-http-c2-redirectors-with-apache-mod_rewrite/) | Design goals, not their configs |
| SSH `-R` / BYO teamserver | [Lorenzo](https://lorenzomeacci.com/creating-a-c2-infrastructure-on-aws) | **Alternate** path if private EC2 is off |
| CloudFront **in front of** a redirector; origin SG = CloudFront prefix list | [Optiv](https://www.optiv.com/insights/discover/blog/redirectors-red-teamers-introduction), [AWS prefix-list blog](https://aws.amazon.com/blogs/networking-and-content-delivery/limit-access-to-your-origins-using-the-aws-managed-prefix-list-for-amazon-cloudfront/) | **v1 origin lock** — SPEC wrongly parked this in v1.5 |
| CloudFront as C2 front (single origin, no S3 decoy) | [RoseSecurity CloudFronting](https://github.com/RoseSecurity/Red-Teaming-TTPs/blob/main/Creative%20C2%20Obfuscation%20-%20CloudFronting%20Through%20Firewalls%20and%20Hiding%20in%20Plain%20PCAP.md), [C2structor](https://github.com/optionalCTF/C2structor) | Proof CF works as edge; **they do not split S3 + nginx** |
| Header token + URI prefixes + scanner block + local decoy HTML | [redStack](https://mintlify.wiki/BaddKharma/redStack/architecture) | Copy the **filter layers**, not Mythic/Sliver/Havoc install |
| Destroy/rebuild burned redirectors | [Red-Terroir](https://github.com/b3n-j4m1n/Red-Terroir) | Burn contract |
| Malleable/profile → nginx | [Malleable-Redirector](https://github.com/inthecyber-group/Malleable-Redirector), [cs2modrewrite](https://github.com/threatexpress/cs2modrewrite/) | **Do not reimplement CS parser.** Optional v1.5 import only |
| Worker + Zero Trust tunnels | [cgomezsec](https://cgomezsec.com/blog/securing-c2-for-rt-operations-using-cloudflare) | ADR / v2 only — **not Terraform v1** |
| S3 + CloudFront + OAC (website) | Your GitBook project; [cloudposse/cloudfront-s3-cdn](https://registry.terraform.io/modules/cloudposse/cloudfront-s3-cdn/aws) | **Decoy origin only** |
| Short vs long haul | [Bluescreen](https://bluescreenofjeff.com/2017-12-05-designing-effective-covert-red-team-attack-infrastructure/), [Cobalt Strike](https://www.cobaltstrike.com/blog/infrastructure-for-ongoing-red-team-operations/) | v1.5 second path/subdomain, not v1 |

### 2.2 What those projects **do not** ship together

Checked against public docs:

| Project | CloudFront | S3 OAC decoy | Path split (site vs callback) | Policy YAML + tests | Burn redirector only | Installs C2 |
|---------|------------|--------------|-------------------------------|---------------------|----------------------|-------------|
| Lorenzo | no | no | no | no | no | operator |
| Trizna | no | wget on disk | no | no | discussed | no |
| Optiv | yes, **one origin** (Apache) | no | no | no | no | no |
| RoseSecurity CF TTP | yes, **one origin** (C2) | no | no | no | no | no |
| C2structor | yes (edge to C2/Caddy) | no split decoy | no | tfvars only | no | **Havoc optional** |
| redStack | **no** | decoy on **Apache disk** | URI → frameworks | tfvars baked into Apache | no dedicated make target | **yes, many** |
| WolfPack | no | Apache AMI | htaccess | no | scale AMIs | no |
| Malleable-Redirector | no infra | no | n/a | profile → nginx | no | no |

**Honest uniqueness:** nobody packages **OAC decoy + gated callback origin + policy CLI with CI + EIP burn**.  
**Not unique:** header gate, UA filter, URI prefix, “Terraform a redirector,” CloudFront in front of C2.

If a reviewer has used redStack, they will say “same filters.” We must say: **filters from redStack/Trizna; edge from Optiv/Rose; decoy storage from S3/OAC (ours as a product).**

---

## 3. What is actually **ours** (keep this short or it is fake)

Only these are worth calling unique:

1. **Split-origin product** — one hostname: humans get S3; callback paths get nginx. (CF multi-origin is a normal AWS feature; **wiring it as a red-team lab with OAC** is the product.)
2. **Framework-agnostic policy engine** — YAML in, nginx out, `validate` / `render` / fixture tests. Not Cobalt-only. Parallel to pst-gate: scanners vs engine; here **nginx vs engine**.
3. **Burn contract that preserves decoy** — replace redirector EC2, **reassociate EIP** (or update origin to new EIP). CloudFront + S3 stay. Domain stays.

**Not unique, do not market as unique:** defender markdown, NON_GOALS.md, IMDSv2, HTTPS viewers, scanner UA lists.

**Purple/detection pack:** keep as **thin docs** (what logs exist). It is not why this repo exists. Harness-friendly; not the core product.

---

## 4. Issues in SPEC.md (fix before coding)

SPEC is a good inventory. It **contradicts itself** and the first code followed the contradictions.

| ID | Problem | Fix |
|----|---------|-----|
| S1 | **I10** world-open 443 **and** **I13** CloudFront-only, mixed v1/v1.5 | If CloudFront is in front, redirector **must not** be world-open. Prefix list = **v1**. |
| S2 | **I15 EIP** is v1 in inventory, **v1.5 in §7** | EIP is **required for burn**. If origin is `public_dns`, replace instance → CF origin breaks. EIP = **v1**. |
| S3 | **I14** private subnet is v1.5; you want **two EC2s** now | Two-EC2 is **v1**. Private teamserver **needs NAT or SSM**. First code put it on public subnet with **no public IP and no NAT** → cannot `apt-get`, cannot SSH from operator CIDR. |
| S4 | **I16** Let’s Encrypt on EC2 **or** CF TLS | **Lock:** CloudFront terminates TLS. Origin **HTTP only**. No Certbot on redirector in v1. |
| S5 | **I10** says port 443; origin HTTP-only needs **port 80** from CloudFront | Ingress: **80 from prefix list**, **22 from operator**. Not 443 from `0.0.0.0/0`. |
| S6 | §7 ships **B1–B7 detection pack in v1** while core burn/EIP still fuzzy | Detection = short `docs/detection.md` in v1, not a pack. |
| S7 | Open decisions **still open** after “start building” | Lock §7 of **this** file first. |
| S8 | “Domain only” vs §6 tfvars | Document **required inputs** (not optional): domain, zone, operator CIDR, SSH key, callback paths. |
| S9 | `nginx if` for header check | Use `map` (nginx docs: `if` is unsafe). Policy renderer must emit `map`. |
| S10 | CloudFront `forwarded_values { headers = ["*"] }` is **legacy** | Callback behavior: managed **CachingDisabled** + **AllViewer** origin request policy ([AWS](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-working-with.websockets.html)). Decoy behavior: cache GET, no POST needed. |
| S11 | CloudFront **origin response timeout** default ~30s | HTTP C2 long-poll can die. Document: this lab is **request/response HTTP**, not long-lived streams. Raise origin read timeout to max (60s) on callback origin. No WebSocket C2 in v1. |
| S12 | Prefix list **weights ~55 / 60 SG rules** | Plan SG: one prefix-list rule + SSH + egress. Do not dump extra CIDRs on the same SG. |
| S13 | CloudFront **VPC origin** (private EC2, no public IP) exists ([AWS](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html), Terraform `aws_cloudfront_vpc_origin`) | **v2 candidate.** Provider still had VPC-origin bugs. v1 = public redirector + EIP + prefix list (known Optiv pattern). |
| S14 | ACM for custom domain on CF **must be us-east-1** | Two AWS providers. First code had this; keep it. |
| S15 | S3 bucket policy needs CF distribution ARN | Standard cycle: create distribution, then policy. Not a blocker if ordered. |

---

## 5. Why the first implementation failed (do not repeat)

Without re-listing files: the undone code had real bugs, not just “too much Terraform.”

1. **Private host with no NAT and no public IP** — dead for packages and SSH.
2. **No EIP** — burn story impossible; CF origin tied to changing DNS.
3. **World-open port 80** — ignored Optiv prefix list.
4. **User-data nginx** handwritten and escaped twice — policy CLI never owned the live config.
5. **Policy YAML not wired into Terraform** — two sources of truth.
6. **No `lab verify`** — could not prove decoy vs gate without AWS.
7. **Scope** tried to look finished while SPEC phases were still mixed.
8. **Opened SSH 22** — you want Session Manager; first code did not.

---

## 5.5 Session Manager (your suggestion)

**Yes. Use it. Close port 22 on both EC2s.**

[Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html): login through AWS CLI/console. **SSM Agent dials out on HTTPS 443.** The instance SG does **not** need inbound 22. [AWS](https://aws.amazon.com/blogs/mt/automated-configuration-of-session-manager-without-an-internet-gateway/): session is outbound; SG is stateful.

Red team already does this: [Red-Formation](https://github.com/scottctaylor12/Red-Formation) — C2 VMs with **no SSH**, `aws ssm start-session`. **Not unique.** Correct for exposure / Harness. Credit them.

| Need | Why |
|------|-----|
| IAM profile `AmazonSSMManagedInstanceCore` on **both** instances | Agent registers |
| SSM Agent (Ubuntu AMI usually has it) | |
| Operator: AWS CLI + [Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) | |
| **No SG rule for 22** | |

**Private teamserver** must still reach SSM APIs:

- **VPC endpoints** `ssm` + `ssmmessages` (+ `ec2messages` on older agents) — **no NAT** for **login** ([AWS docs](https://docs.aws.amazon.com/systems-manager/latest/userguide/setup-create-vpc.html)).
- Downloading C2 from the public internet still needs **NAT or S3**. v1: endpoints for SSM; optional `enable_nat` later. Operator can S3-drop the binary.

**Redirector** stays on a public subnet (EIP for CloudFront). Agent uses IGW outbound 443. **Still no inbound 22.** Inbound **:80 only from CloudFront prefix list**.

SSM port-forward for C2 UIs (same as Red-Formation): `AWS-StartPortForwardingSession`.

SSM does **not** replace CloudFront or nginx. Public surface remains **CF :443**.

---

## 6. Locked architecture (proposed — accept or change here)

```text
                    Internet
                       │
                       ▼
              Route 53 + ACM (us-east-1)
                       │
                       ▼
                   CloudFront
          ┌────────────┴────────────┐
          │                         │
   default /*                  ordered /cdn/* (configurable)
   GET/HEAD cached             CachingDisabled + AllViewer
          │                         │
          ▼                         ▼
   S3 decoy (OAC)            Redirector EC2
   private bucket            public subnet + EIP
                             SG: :80 from CF prefix list
                                 NO :22
                             nginx from policy YAML
                             SSM Agent → IGW :443
                                    │
                                    ▼
                             Teamserver EC2 (BYO)
                             private subnet, no public IP
                             SG: redirector SG → listen port only
                                 NO :22
                             SSM via VPC endpoints (ssm, ssmmessages)
```

**EC2 count: two.** Admin: `aws ssm start-session --target <id>` on either.

| Host | Internet inbound | Role |
|------|------------------|------|
| Redirector | :80 from CloudFront IPs only | nginx gate |
| Teamserver | none | You install C2 |

**Burn:** replace redirector instance **and EIP**; CloudFront origin follows.

**Not in v1:** Cloudflare Worker, Lambda, VPC origin, Packer, fleet, long-haul domain, C2 install, Certbot, **SSH**.

---

## 7. Decisions to lock (SPEC §9 + extras)

| # | Decision | **Lock** |
|---|----------|----------|
| 1 | Architecture | **3.1 split-origin** (one domain). Two-hostname fallback if CF callback path fails dogfood. |
| 2 | Origin TLS | **HTTP-only** behind CloudFront. CF = HTTPS to clients. |
| 3 | Proxy server | **nginx** |
| 4 | Repo name | **`c2-edge-lab`** (product). Split-origin is the **architecture**, not the GitHub name. |
| 4b | How we say it | **Automated C2 infrastructure** — domain, decoy, redirector, policy, burn. Not “installs C2 for you.” |
| 5 | Teamserver | **Second private EC2**, C2 not installed |
| 6 | Admin | **Session Manager, no port 22** on either instance |
| 7 | Private SSM | **VPC endpoints** (no NAT required for login) |
| 8 | Redirector data plane | **:80 from CloudFront prefix list only** |
| 9 | Burn | **New EIP** + new instance; CloudFront origin follows |
| 10 | Policy | **One YAML** → nginx (boot + CLI) |
| 11 | Detection | **One markdown file** |
| 12 | Lambda / Cloudflare TF | **Out** |
| 13 | NAT | **Off in v1** (optional flag later for apt/C2 download) |
| 14 | Inputs | Not domain-only. See §8. |

---

## 8. Required inputs (honest)

| Input | Required | Why |
|-------|----------|-----|
| AWS credentials + region | yes | IAM can `ssm:StartSession` |
| `domain_name` | yes | CF alias |
| `hosted_zone_id` | yes | ACM DNS + A/AAAA alias |
| `callback_path_patterns` | yes | e.g. `/cdn/*` |
| Header name + empty-or-set token | yes | Gate |
| `lab.tfvars` | yes | Never commit secrets |

**Not required if SSM is locked:** `operator_cidr`, `ssh_key_name`.

VPC endpoints + two t3.micro + CF + S3 still cost money. NAT is **optional**, not default.

---

## 9. Low-level build order (when you say go)

**Implement against [BUILD.md](BUILD.md)** (file tree, policy schema, nginx contract, Terraform names, user-data, proofs). This table is the index only.

Do **not** write all Terraform in one shot. Each step must be testable.

| Step | Deliverable | Proof |
|------|-------------|--------|
| 0 | Align SPEC with this freeze (SSM, no 22, EIP, prefix list, two-EC2) | Spec matches — **done in BUILD pass** |
| 1 | Policy schema + CLI: validate, render-nginx, tests + `nginx -t` in CI | No AWS |
| 2 | S3 + OAC + CF **decoy only** | `https://domain/` shows decoy |
| 3 | VPC: public + private + **SSM VPC endpoints** + SGs (prefix list, **no 22**) | Plan shows endpoints, no SSH rule |
| 4 | Both EC2s + instance profiles; redirector **EIP**; policy user-data | `aws ssm start-session`; curl :80 gate |
| 5 | CF second origin + CachingDisabled/AllViewer | Browser decoy; curl with header hits nginx |
| 6 | `lab verify` | CI mock + optional live |
| 7 | `make burn-redirector` (replace + EIP) | Decoy URL unchanged |
| 8 | README credits + NON_GOALS + thin detection doc | |

If step 5 fails (CF strips headers / caches POST), **fallback:** architecture 3.2 — decoy on CF/S3, callbacks **direct to EIP** (Lorenzo + Optiv without path split). Uniqueness drops; product still works.

---

## 10. What we will **not** research further for v1

Already decided **out**: SpotifyC2, Evilginx, Gophish, multi-cloud, domain fronting, Function URL C2, redStack C2 zoo, wget clones, AI Terraform, Guacamole, **inbound SSH**.

---

## 11. Neutral scores (after this pass)

| Lens | Score | Note |
|------|-------|------|
| Uniqueness vs public GitHub | **7/10** as a **combo**; **4/10** per feature | Combo is the pitch |
| Engineering risk | **High** until CF callback path is dogfooded | Timeouts, cache, headers |
| Fit as Harness project #3 | **6.5/10** as C2 **infra** + OAC + policy; weaker if it sounds like a Havoc installer | pst-gate remains hero |
| Chance first-apply works if we skip §9 | **Low** | That was the undone attempt |

---

## 12. Ask before code

If **BUILD.md** is accepted, next is **Step 1 only** (policy engine, no AWS) — not all Terraform at once.
