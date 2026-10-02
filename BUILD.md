# BUILD.md — low-level implementation playbook

**Repo name (locked):** `c2-edge-lab`  
**Headline:** Automated **C2 infrastructure** on AWS (CloudFront split-origin: S3 decoy + gated nginx). Teamserver is **BYO** — we do not install Havoc/Sliver/Mythic.

**Status:** Step 9 (second haul, S3 copy-in, hostname burn, SSM port-forward, thicker decoy) is in the tree. **Never `terraform apply` unless the operator asks.** Playbook steps 1–8 plus these extras.  
**Read with:** [ANALYSIS.md](ANALYSIS.md) (why / unique thing) · [SPEC.md](SPEC.md) (inventory, after freeze alignment)

This file is what you implement against. If SPEC and this disagree, **this file wins**.

---

## 1. What v1 actually is

One `terraform apply` that **automates the C2 edge** (domain, decoy, redirector, policy, burn):

1. **CloudFront** on your domain.
2. **Default `/*`** → private **S3** decoy via **OAC**.
3. **Ordered `/cdn/*`** (configurable) → **nginx** on a public **redirector EC2** (EIP, port **80** only from CloudFront prefix list).
4. nginx **proxies only** if policy matches (header + path + UA); else **local decoy HTML**.
5. Backend is a **private teamserver EC2** (no public IP). You install C2 later. v1 ships a **stdlib echo** on `:8080` so verify works without a framework.
6. Login is **SSM Session Manager**. **No port 22.**
7. **`lab` CLI** owns policy YAML → nginx. CI runs `nginx -t`.
8. **`make burn-redirector`** replaces the redirector **instance and EIP**; CloudFront origin follows the new IP; S3 + the CF hostname stay.

That is the unique product. Filters/SSM/CF-in-front are borrowed. Do not add “cool” extras in the same PR as the first apply.

---

## 2. Frozen decisions (do not re-open in code)

| Topic | Lock |
|-------|------|
| Architecture | Two CloudFront hostnames, split origin each (same two EC2s) |
| EC2 count | **Two** (redirector + teamserver) |
| Admin | SSM, **no SG rule for 22** |
| Redirector inbound | **:80 from CloudFront managed prefix list only** |
| Origin TLS | CloudFront terminates HTTPS. Origin is **HTTP** |
| Certbot / Let’s Encrypt on EC2 | **Out** |
| Redirector origin identity | **EIP** (CloudFront origin). Identity burn allocates a new one |
| Teamserver | Private subnet, **no public IP**, **no NAT** in v1 |
| Private SSM | Interface endpoints: `ssm`, `ssmmessages`, `ec2messages` |
| Proxy | **nginx** |
| nginx `if` + `proxy_pass` | **Forbidden.** Use `map` + named locations |
| Policy | One YAML → one nginx conf. Terraform does **not** hand-write maps |
| Detection | **One** file: `docs/detection.md` |
| C2 install | **Out.** Echo stub only |
| Cloudflare / Lambda / VPC origin / Packer / fleet | **Out** |
| Repo / GitHub name | **`c2-edge-lab`** |
| How we say it | **“Automated C2 infrastructure”** is the product line. Not “one-click Havoc.” |
| Fallback if path-split fails dogfood | Architecture 3.2 (two hostnames) — separate decision, not mixed into v1 code |
| Terraform state | Existing S3 bucket; name in gitignored `terraform/config.s3.tfbackend`. No local state. CI stays `-backend=false`. |

---

## 3. Request walk (implement this, nothing else)

| Client request | CloudFront | nginx | Result |
|----------------|------------|-------|--------|
| `GET https://domain/` | default behavior → S3 | not involved | decoy site |
| `GET https://domain/cdn/x` missing header | ordered behavior → EIP:80 | maps fail | **local** decoy HTML (200) |
| `GET https://domain/cdn/x` scanner UA | same | scanner map | local decoy (v1; not 444) |
| `GET https://domain/cdn/x` header + allowed UA | same | maps pass | `proxy_pass` private IP:8080 |
| SSM `start-session` | not involved | not involved | login, no 22 |

Failed `/cdn/*` **cannot** fall back to S3. CloudFront already chose the nginx origin. Local decoy on the box is required.

---

## 4. Repo tree (create only these in v1)

```text
c2-edge-lab/
  ANALYSIS.md
  SPEC.md
  BUILD.md
  README.md
  NON_GOALS.md
  CHANGELOG.md
  Makefile
  pyproject.toml
  lab.tfvars.example
  .gitignore
  docs/
    architecture.md
    adopt.md
    detection.md
  policy/
    redirector.policy.yaml          # committed example (no real secret)
    schema.json                     # JSON Schema for validate
  decoy/
    index.html
    robots.txt
    favicon.ico                     # tiny placeholder
  src/c2_edge_lab/
    __init__.py
    cli.py                          # lab policy / lab verify
    policy.py                       # load + validate
    nginx_render.py                 # YAML → nginx text
    templates/
      redirector.conf.j2
      decoy.html                    # same text nginx serves on deny
  tests/
    test_policy.py
    test_nginx_render.py
    test_cli.py
    fixtures/
      policy.valid.yaml
      policy.bad.yaml
      expected.conf.fragment
  terraform/
    versions.tf
    backend.tf                      # partial S3 backend (empty bucket/key/region)
    config.s3.tfbackend.example     # copy locally; do not commit the real bucket
    providers.tf                    # default + alias aws.us_east_1
    variables.tf
    outputs.tf
    vpc.tf
    endpoints.tf                    # SSM interface endpoints
    iam.tf
    s3.tf
    acm.tf
    dns.tf
    cloudfront.tf
    sg.tf
    redirector.tf                   # instance + EIP + association
    teamserver.tf
    user_data/
      redirector.sh.tftpl           # tiny: install nginx, write conf, enable
      teamserver.sh.tftpl           # tiny: echo stub on 8080
  generated/
    .gitkeep
    redirector.conf                 # gitignored; produced by CLI
  .github/workflows/
    ci.yml
```

**Do not create:** Packer, Cloudflare, Lambda, `docs/detection/` folder of many files, SSH key resources, NAT gateway.

---

## 5. Policy schema (v1)

`policy/redirector.policy.yaml` — the only operator-facing filter file.

```yaml
version: 1
header:
  name: X-Lab-Token          # CloudFront AllViewer forwards this
  value: ""                  # empty → CLI/Terraform generates; never commit a real secret
paths:
  prefixes:
    - /cdn/                  # must match CloudFront ordered behavior
user_agents:
  allow_exact:
    - "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabCallback/1.0"
  allow_regex: []            # v1: keep empty unless tests cover it
  scanner_substrings:
    - curl
    - wget
    - nikto
    - nmap
    - masscan
    - sqlmap
    - python-requests
    - Go-http-client
backend:
  port: 8080                 # host is injected at render time (teamserver private IP)
decoy:
  root: /var/www/html
  index: index.html
```

**Validate rules:**

- `version` must be `1`
- `header.name` HTTP token (no spaces)
- `paths.prefixes` non-empty; each starts with `/`
- at least one `allow_exact` **or** `allow_regex`
- `backend.port` 1–65535
- unknown keys = error (fail closed)

**Render-time extra (not in YAML):** `--backend-host 10.42.2.x` from Terraform output / `lab verify`.

Empty `header.value`: `lab policy render-nginx` refuses unless `--allow-empty-header` (lab-open) **or** value is passed via env `C2_EDGE_HEADER_VALUE` at apply. Terraform generates `random_password` and passes it in. Example YAML in git stays empty.

---

## 6. nginx contract (the renderer must emit this shape)

Canonical template: `src/c2_edge_lab/templates/redirector.conf.j2`

Rules:

- `map` for header ok / UA class / combined action
- **No** `if` around `proxy_pass`
- Deny → named location `@decoy`
- Allow → named location `@proxy`
- `default_server` so `Host: your.domain` from AllViewer still matches
- `proxy_http_version 1.1`; `proxy_set_header Host $host`; `proxy_set_header Connection ""`
- `proxy_read_timeout 60s` (match CloudFront origin read timeout)
- listen **80** only
- `server_tokens off`

Shape (illustrative, not copy-paste forever):

```nginx
map $http_x_lab_token $sol_header_ok {
    default 0;
    "GENERATED_OR_INJECTED_VALUE" 1;
}

map $http_user_agent $sol_ua_class {
    default other;
    ~*(curl|wget|nikto|nmap|masscan|sqlmap|python-requests|Go-http-client) scanner;
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabCallback/1.0" allow;
}

map "$sol_header_ok:$sol_ua_class" $sol_gate {
    default decoy;
    "1:allow" proxy;
}

server {
    listen 80 default_server;
    server_name _;
    root /var/www/html;

    location /cdn/ {
        error_page 418 = @proxy;
        error_page 419 = @decoy;
        if ($sol_gate = proxy) { return 418; }
        return 419;
    }

    location / {
        try_files /index.html =200;
    }

    location @proxy {
        proxy_pass http://BACKEND_HOST:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 60s;
    }

    location @decoy {
        try_files /index.html =200;
    }
}
```

`if` is allowed **only** as `return 418/419` to named locations (nginx-safe pattern). Never `if { proxy_pass }`.

Path prefixes from YAML become `location` blocks (one per prefix). CloudFront already filters which requests arrive; nginx still enforces prefixes so a mis-set behavior cannot open `/`.

---

## 7. Python CLI (`lab`)

Package: `c2_edge_lab`  
Entry: `lab`

| Command | Exit | Does |
|---------|------|------|
| `lab policy validate -f policy/redirector.policy.yaml` | 0 / 2 | schema |
| `lab policy render-nginx -f … --backend-host HOST -o generated/redirector.conf` | 0 / 2 | writes conf |
| `lab policy test -f …` | 0 / 1 | fixture table (no AWS) |
| `lab verify --base-url URL --header-name --header-value --path` | 0 / 1 | live HTTP checks |

`lab policy test` cases (pytest + optional in-process):

| Request | Expect |
|---------|--------|
| path `/` (unit: nginx not involved) | n/a at unit; live verify covers S3 |
| `/cdn/x` no header | decoy (renderer includes gate) |
| `/cdn/x` scanner UA + good header | decoy |
| `/cdn/x` good header + allow UA | proxy upstream in conf |
| unknown YAML key | validate fail |

CI: render fixture → `nginx -t -c` against a wrapper that includes the snippet (install nginx in the runner **or** `nginx:alpine` in a job). Prefer a job that `docker run nginx:alpine nginx -t`.

---

## 8. Terraform: resource names and apply order

**Providers**

- `aws` → `var.aws_region` (default `us-east-1`)
- `aws.us_east_1` → always `us-east-1` for ACM + CloudFront cert

**VPC (`vpc.tf`)**

| Resource | Name | Notes |
|----------|------|-------|
| `aws_vpc.lab` | `10.42.0.0/16` | DNS hostnames on |
| `aws_subnet.public` | `10.42.1.0/24` | map public IP **true** (redirector) |
| `aws_subnet.private` | `10.42.2.0/24` | map public IP **false** |
| `aws_internet_gateway.lab` | | |
| `aws_route_table.public` | 0.0.0.0/0 → IGW | |
| `aws_route_table.private` | **no NAT, no default internet** | local only + prefix-list to endpoints |
| `aws_eip.redirector` | `vpc = true` | created **before** instance association; **replaced** on identity burn |

**Endpoints (`endpoints.tf`)** — private subnet, private DNS on

- `com.amazonaws.<region>.ssm`
- `com.amazonaws.<region>.ssmmessages`
- `com.amazonaws.<region>.ec2messages`

SG `aws_security_group.endpoints`: ingress **443 from VPC CIDR**; no 22.

Optional later: S3 **gateway** endpoint so private host can pull objects. **Not** required for v1 echo stub.

**Security groups (`sg.tf`)**

| SG | Ingress | Egress |
|----|---------|--------|
| `redirector` | **80** from `data.aws_ec2_managed_prefix_list.cloudfront` (`com.amazonaws.global.cloudfront.origin-facing`) | 443 0.0.0.0/0 (apt + SSM); `teamserver_port` to `sg.teamserver` |
| `teamserver` | `var.teamserver_listen_port` **from redirector SG only** | 443 to VPC CIDR (SSM endpoints) |
| **Neither has 22** | | |

Do **not** add extra CIDRs on the redirector SG (prefix list is ~55 rules / 60 max).

**IAM (`iam.tf`)**

- Instance profile + role on **both** EC2s
- Attach **only** `AmazonSSMManagedInstanceCore`
- No SSH key pair resource

**Redirector (`redirector.tf`)**

- Ubuntu AMI with SSM Agent (data source `ubuntu` 24.04)
- `t3.micro`, public subnet, **associate public IP** *and* **EIP association** (EIP is the stable CloudFront origin)
- IMDSv2 **required** (`http_tokens = required`)
- User data from `redirector.sh.tftpl` with `nginx_conf` = contents of `generated/redirector.conf` (see §9)
- `depends_on` EIP + IAM profile

**Teamserver (`teamserver.tf`)**

- Same AMI, **private** subnet, `associate_public_ip_address = false`
- Same instance profile
- User data: bind `python3 -m http.server` **or** a 10-line TCP script on `0.0.0.0:8080` returning `teamserver-ok` — **stdlib only** (AMI already has Python; **no apt**, no NAT)

**S3 + OAC (`s3.tf`)**

- Private bucket, no ACL public
- `aws_s3_object` for `decoy/*`
- OAC
- Bucket policy: `s3:GetObject` from **this** CloudFront distribution ARN only
- Order: bucket + OAC → distribution → bucket policy (standard cycle)

**ACM + DNS (`acm.tf`, `dns.tf`)**

- Cert in **us-east-1**, DNS validation on `var.hosted_zone_id`
- Route53 A/AAAA alias to CloudFront

**CloudFront (`cloudfront.tf`)**

| Setting | Value |
|---------|--------|
| Origins | S3 (OAC) + custom `var.eip` HTTP port 80, `origin_protocol_policy = http-only` |
| Origin read timeout (callback) | **60** |
| Default behavior | S3, GET/HEAD, cache OK, viewer HTTPS redirect |
| Ordered behavior | `var.callback_path_patterns` (e.g. `/cdn/*`), origin = redirector, **CachingDisabled**, **AllViewer** origin request (looked up **by name**, not hardcoded UUID, not legacy `forwarded_values`) |
| Viewer | redirect-to-https, TLS 1.2 min |
| Alias | Optional: `var.domain_name` + ACM when both domain + zone are set; otherwise CloudFront default cert / `dxxxx.cloudfront.net` |

Managed policies — Terraform data sources, **not** pasted IDs (IDs are easy to mix up; `59781a5b` is CORS-CustomOrigin, not AllViewer):

- `Managed-CachingOptimized` (S3 decoy)
- `Managed-CachingDisabled` (callback path)
- `Managed-AllViewer` (callback origin request — forwards `X-Lab-Token`)
- `Managed-SecurityHeadersPolicy` (decoy responses only)

**Outputs**

- `decoy_url` = `https://${domain}/`
- `callback_example` = `https://${domain}/cdn/`
- `redirector_instance_id`, `teamserver_instance_id`
- `ssm_redirector` = `aws ssm start-session --target …`
- `ssm_teamserver` = same
- `header_name` (not the secret)
- `eip`

**No output of:** header secret (put in SSM Parameter optional v1.5). For v1, `terraform output -raw header_value` is acceptable **locally**; never log it in CI.

---

## 9. How nginx gets onto the box (do not repeat user-data hell)

**Single source of truth:** Python renderer.

**Apply path:**

1. Operator (or Makefile) runs  
   `lab policy render-nginx -f policy/redirector.policy.yaml --backend-host $(terraform output -raw teamserver_private_ip) --header-value $VAL -o generated/redirector.conf`  
   First apply chicken-egg: backend host is unknown until teamserver exists.

**Break the chicken-egg without dual configs:**

- **Pass 1 / same apply:** Terraform knows `aws_instance.teamserver.private_ip` **inside** the same graph.
- Do **not** call Python from `data.external` if you can avoid it (fragile on Windows/WSL paths).
- **Lock:** Terraform `templatefile` is **not** the nginx author.
- **Lock:** `null_resource.nginx_conf` `local-exec` runs the CLI with `-backend-host ${aws_instance.teamserver.private_ip}` **before** redirector user-data is hashed.
- Redirector `user_data` = small shell + `base64decode` of that generated file.

If `local-exec` is too flaky on first dogfood, **allowed escape:** Terraform writes YAML + backend host into user-data as **two files** (`/etc/c2-edge/policy.yaml`, `/etc/c2-edge/backend.env`) and user-data runs a **copied** `nginx_render.py` **stdlib-only** (no pip). That means the renderer must stay **stdlib** (no Pydantic, no PyYAML if we vendor a tiny loader — **prefer PyYAML in CLI for CI**, and a **second** stdlib renderer is a footgun).

**Chosen lock (simplest that survived the last failure):**

- Renderer stays in Python with PyYAML **on the operator machine**.
- Terraform uses `templatefile` **only** as a thin wrapper: it substitutes `{{ backend_host }}` and `{{ header_value }}` into the **already rendered** conf from CI fixture **or** Makefile target `make conf`.
- Makefile:

```text
conf:
	lab policy render-nginx -f policy/redirector.policy.yaml \
	  --backend-host PLACEHOLDER --header-value PLACEHOLDER \
	  -o generated/redirector.conf
```

- Terraform `replace()` on `PLACEHOLDER` tokens with `aws_instance.teamserver.private_ip` and `random_password.header.result`.
- User-data copies the **substituted** string to `/etc/nginx/sites-available/redirector`, `ln -s`, `nginx -t`, `systemctl enable --now nginx`.
- User-data **must not** contain nested nginx maps typed by hand in HCL.

Redirector **can** `apt-get install nginx` (public subnet + IGW).

Teamserver **cannot** apt-get. Echo uses `/usr/bin/python3` from the AMI.

---

## 10. Build order (implement in this order, stop if proof fails)

Each step is a PR-sized chunk. Do not start step N+1 until the proof column is true.

### Step 0 — docs freeze (this change set)

- [ ] SPEC.md matches this file (SSM, no 22, EIP v1, prefix list v1, HTTP origin, two EC2, thin detection, inputs)
- [ ] ANALYSIS.md §9 points here
- **Proof:** no remaining SPEC row that says SSH-from-CIDR or world-open 443 for v1

### Step 1 — policy engine (no AWS)

Create: `pyproject.toml`, package, schema, fixtures, tests, `ci.yml` (ruff + pytest + nginx -t).

**Proof:** `pytest` green; `lab policy render-nginx` output passes `nginx -t` in CI; bad YAML exit 2.

### Step 2 — S3 + OAC + CloudFront decoy only

Terraform: providers, ACM, DNS, S3, OAC, **single-origin** distribution (temporary). No EC2 yet.

**Proof:** `https://domain/` shows `decoy/index.html`. Bucket is not public.

### Step 3 — VPC + SGs + SSM endpoints

Add vpc, subnets, IGW, prefix list data, SGs, endpoints. Still no EC2 **or** add throwaway instances to test SSM then destroy.

**Proof:** `terraform plan` shows **no** `ingress` 22; prefix list on :80; three interface endpoints.

### Step 4 — both EC2s + EIP + user-data

Redirector nginx from generated conf (backend = teamserver private IP). Teamserver echo on 8080.

**Proof:**

```bash
aws ssm start-session --target "$REDIRECTOR_ID"
aws ssm start-session --target "$TEAMSERVER_ID"
```

From a helper: `curl -H "Host: domain" http://$EIP/cdn/x` **without** header → decoy.  
With header + UA → `teamserver-ok`.  
`curl http://$EIP/` is **not** a public test you rely on (SG should **refuse** non-CloudFront). For SG proof, curl from your laptop to EIP:80 **must fail**. Gate test: SSM on redirector `curl localhost` **or** temporarily (never commit) — **do not** open 80 to 0.0.0.0/0 even for debug. Use SSM port-forward:

```bash
aws ssm start-session --target "$REDIRECTOR_ID" \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["80"],"localPortNumber":["18080"]}'
curl -H "Host: example" http://127.0.0.1:18080/cdn/x
```

### Step 5 — CloudFront second origin (the unique thing)

Add ordered behavior + custom origin = EIP. CachingDisabled + AllViewer. Origin timeout 60s.

**Proof:**

| Command | Expect |
|---------|--------|
| `curl -sS https://domain/` | S3 decoy HTML |
| `curl -sS https://domain/cdn/probe` | nginx decoy (no token) |
| `curl -sS -H "X-Lab-Token: …" -A "…LabCallback/1.0" https://domain/cdn/probe` | `teamserver-ok` |
| Same with `-A curl` | nginx decoy, not echo |

If header never reaches nginx: check origin request policy is **AllViewer**, not AllViewerExceptHostHeader, and header name matches `map $http_x_lab_token`.  
If POST/cache issues: confirm CachingDisabled on the ordered behavior only.

**If this step fails after a real debug pass:** stop. Switch to architecture 3.2 (do not silently mix). Uniqueness drops; product still ships.

### Step 6 — `lab verify`

CLI hits the four URLs above. Makefile `lab-verify` reads Terraform outputs (operator-only; not CI). Pytest injects a `fetch_fn` so CI never talks to AWS.

**Proof:** `tests/test_verify.py` green + four red paths; README green vs red curl-UA example.

### Step 7 — burn

`make burn-redirector` prints `terraform apply -replace=aws_instance.redirector -replace=aws_eip.redirector` and **refuses to apply**. That is **identity burn**: new VM, new origin IP. CloudFront origin is `aws_eip.redirector.public_ip`, so the distribution updates in place (`wait_for_deployment`). S3 and the CloudFront hostname stay. User-data re-applies nginx on the new VM.

Host-only replace (`-replace=aws_instance.redirector` with the EIP kept) is a quieter disk swap. It is **not** redirector burn.

**Proof (CI):** `tests/test_burn.py` — EIP has no `instance =`, CF origin is the EIP (so origin follows a new allocation), Makefile `-replace`s both addresses, no `create_before_destroy` (one EIP cannot bind two instances).

**Proof (live, after an apply you run):** instance id, `redirector_eip`, and `redirector_eip_allocation_id` all change; decoy URL (CloudFront hostname) does not; `make lab-verify` still green after the distribution deploys.

### Step 8 — docs for humans

README (what / authorized only / credits / unique sentence), NON_GOALS, architecture diagram, adopt (inputs), detection.md (what logs exist — CF via / x-amz-cf-id, origin prefix list, nginx maps). Comparison table vs Lorenzo / Optiv / redStack / C2structor.

**Proof:** `docs/adopt.md` is the apply path. `tests/test_docs.py` checks the four files and the adopt/detect/compare needles.

---

## 11. Required inputs (`lab.tfvars.example`)

```hcl
# Hostname: leave both empty for CloudFront default (dxxxx.cloudfront.net).
# Set both for a custom domain (ACM + Route 53).
domain_name    = ""
hosted_zone_id = ""
# domain_name    = "lab.example.com"
# hosted_zone_id = "ZXXXXXXXX"

aws_region = "us-east-1"
acm_region = "us-east-1"   # CloudFront certs; do not change

vpc_cidr            = "10.42.0.0/16"
public_subnet_cidr  = "10.42.1.0/24"
private_subnet_cidr = "10.42.2.0/24"

instance_type    = "t3.micro"
root_volume_type = "gp3"
root_volume_size = 8

callback_path_patterns              = ["/cdn/*"]
cloudfront_minimum_protocol_version = "TLSv1.2_2021"

# Must match `make conf`:
nginx_backend_placeholder = "192.0.2.1"
nginx_header_placeholder  = "PLACEHOLDERHEADER"
```

**Not in v1 tfvars:** `operator_cidr`, `ssh_key_name`, NAT flags (unless `enable_nat` default **false** for later).

Operator needs: AWS creds, Route53 zone, ACM/DNS rights, `ssm:StartSession`, Session Manager plugin.

---

## 12. Makefile targets (v1)

| Target | Action |
|--------|--------|
| `make test` | ruff + pytest |
| `make conf` | render nginx to `generated/` |
| `make lab-up` | `terraform apply -var-file=lab.tfvars` (after conf) |
| `make lab-verify` | `lab verify` using outputs |
| `make burn-redirector` | prints `-replace` instance **and** EIP; **does not apply** |
| `make lab-down` | `terraform destroy` |

---

## 13. Coding rules (first-attempt bugs — checklist in every PR)

1. No inbound **22**
2. No **NAT** unless flag later
3. No world-open **80/443** on EC2
4. EIP exists before CloudFront origin uses an IP
5. Private instance: SSM endpoints **and** Python already on AMI
6. User-data does not nest a handwritten nginx server block in HCL
7. Policy YAML is the only filter source
8. Do not install Havoc/Sliver/Mythic
9. Do not add Cloudflare/Lambda “while we’re here”
10. ACM in us-east-1
11. Prefix list only on redirector :80 — don’t add operator CIDR “just in case”
12. `generated/redirector.conf` gitignored except `.gitkeep`

---

## 14. Definition of done (v1)

- [ ] Steps 1–8 proofs all true on one AWS account
- [ ] CI green without AWS secrets
- [ ] Burn keeps decoy URL
- [ ] README headline: **automated C2 infrastructure**; credits Trizna, Optiv, redStack filters, Red-Formation SSM; unique sentence is CloudFront **S3 OAC decoy + gated nginx path**
- [ ] Resume **may** say automated C2 infrastructure (Terraform + CloudFront + OAC + policy redirector). pst-gate stays the **hero** bullet; this is project #3

When this file is accepted, implement **Step 0 leftovers then Step 1 only**.
