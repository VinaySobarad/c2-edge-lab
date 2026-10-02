# c2-edge-lab

Automated **C2 infrastructure** on AWS: two CloudFront hostnames (short-haul + long-haul), an **S3 decoy** for humans, and a **policy-gated nginx redirector** for callback paths. You install the teamserver. This repo does not.

**Unique piece:** CloudFront splits origins — `/*` is a private S3 site (OAC); `/cdn/*` (short) and `/lh/*` (long, second `dxxxx`) are nginx. Burn the redirector (new VM + new EIP); keep the decoy. Burn the short-haul hostname separately; long-haul stays.

Authorized lab only. You must own the AWS account. A custom domain is optional.

## Verify after apply

Hostnames, EIPs, and the gate token are Terraform outputs. They are **not** in git. Load them, then run the curls:

```bash
CLOUDFRONT_URL="$(terraform -chdir=terraform output -raw decoy_url)"
CLOUDFRONT_LONGHAUL_URL="$(terraform -chdir=terraform output -raw longhaul_url)"
PUBLIC_EC2_IP="$(terraform -chdir=terraform output -raw redirector_eip)"
TEAMSERVER_IP="$(terraform -chdir=terraform output -raw teamserver_private_ip)"
TOKEN="$(terraform -chdir=terraform output -raw lab_header_value)"
```

| Variable | Role |
|----------|------|
| `CLOUDFRONT_URL` | short-haul (`/*` → S3, `/cdn/*` → nginx) |
| `CLOUDFRONT_LONGHAUL_URL` | long-haul (`/*` → S3, `/lh/*` → nginx) |
| `PUBLIC_EC2_IP` | redirector EIP — **must time out** from a laptop |
| `TEAMSERVER_IP` | private teamserver; nginx origin, not on the internet |

What to look at so this cannot be waved off as “just a static site”:

- Every HTTPS response has `via: … (CloudFront)` and `x-amz-cf-id`.
- Human `/` is S3: `content-type: text/html; charset=utf-8`, **no** `server: nginx`.
- Failed `/cdn/*` and `/lh/*` are nginx: `content-type: text/html` (no charset), **`server: nginx`**, same 704-byte page.
- Only header **plus** the exact LabCallback UA returns `text/plain; charset=utf-8`, `content-length: 13`, body `teamserver-ok`.
- Token + `curl` UA is still decoy (scanner map).
- `https://…/stage/sliver-server` is **403 AccessDenied** from AmazonS3 (staged binaries are not on the decoy URL).
- Laptop → EIP times out (prefix list, not `0.0.0.0/0`).

Decoy HTML (704 bytes) returned by every failed check below:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Northline Analytics</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" href="/app.css" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  </head>
  <body>
    <header>
      <p id="decoy-stamp">Northline Analytics</p>
    </header>
    <main>
      <h1>Operational research for infrastructure teams</h1>
      <p>
        We publish notes on CDN design, object storage, and change control.
        This page is a static lab decoy — it does not collect credentials.
      </p>
    </main>
    <script src="/app.js"></script>
  </body>
</html>
```

### 1. Short-haul decoy (humans, `/`) — S3

```bash
curl -sS -D - "$CLOUDFRONT_URL"
```

```
HTTP/2 200
content-type: text/html; charset=utf-8
content-length: 704
x-cache: RefreshHit from cloudfront
via: 1.1 <edge>.cloudfront.net (CloudFront)
x-amz-cf-pop: <POP>
x-amz-cf-id: <id>
```

Body: the 704-byte Northline HTML above. No `server: nginx`.

### 2. Short-haul `/cdn/probe` — allowed UA, **no** token — nginx decoy

```bash
curl -sS -D - \
  -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabCallback/1.0' \
  "${CLOUDFRONT_URL%/}/cdn/probe"
```

```
HTTP/2 200
content-type: text/html
content-length: 704
server: nginx
x-cache: Miss from cloudfront
via: 1.1 <edge>.cloudfront.net (CloudFront)
x-amz-cf-pop: <POP>
x-amz-cf-id: <id>
```

Body: same 704-byte Northline HTML. Not `teamserver-ok`.

### 3. Short-haul `/cdn/probe` — valid token, **scanner** UA

```bash
curl -sS -D - \
  -A 'curl/8.4.0' \
  -H "X-Lab-Token: $TOKEN" \
  "${CLOUDFRONT_URL%/}/cdn/probe"
```

```
HTTP/2 200
content-type: text/html
content-length: 704
x-cache: Miss from cloudfront
via: 1.1 <edge>.cloudfront.net (CloudFront)
x-amz-cf-pop: <POP>
x-amz-cf-id: <id>
```

Body: same 704-byte Northline HTML. Not `teamserver-ok`.

### 4. Short-haul `/cdn/probe` — valid token **and** allowed UA

```bash
curl -sS -D - \
  -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabCallback/1.0' \
  -H "X-Lab-Token: $TOKEN" \
  "${CLOUDFRONT_URL%/}/cdn/probe"
```

```
HTTP/2 200
content-type: text/plain; charset=utf-8
content-length: 13
x-cache: Miss from cloudfront
via: 1.1 <edge>.cloudfront.net (CloudFront)
x-amz-cf-pop: <POP>
x-amz-cf-id: <id>

teamserver-ok
```

### 5. Long-haul decoy (humans, `/`) — S3 on the second hostname

```bash
curl -sS -D - "$CLOUDFRONT_LONGHAUL_URL"
```

```
HTTP/2 200
content-type: text/html; charset=utf-8
content-length: 704
x-cache: RefreshHit from cloudfront
via: 1.1 <edge>.cloudfront.net (CloudFront)
x-amz-cf-pop: <POP>
x-amz-cf-id: <id>
```

Body: same 704-byte Northline HTML. No `server: nginx`.

### 6. Long-haul `/lh/probe` — allowed UA, **no** token — nginx decoy

```bash
curl -sS -D - \
  -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabCallback/1.0' \
  "${CLOUDFRONT_LONGHAUL_URL%/}/lh/probe"
```

```
HTTP/2 200
content-type: text/html
content-length: 704
x-cache: Miss from cloudfront
via: 1.1 <edge>.cloudfront.net (CloudFront)
x-amz-cf-pop: <POP>
x-amz-cf-id: <id>
```

Body: same 704-byte Northline HTML. Not `teamserver-ok`.

### 7. Long-haul `/lh/probe` — valid token, **scanner** UA

```bash
curl -sS -D - \
  -A 'curl/8.4.0' \
  -H "X-Lab-Token: $TOKEN" \
  "${CLOUDFRONT_LONGHAUL_URL%/}/lh/probe"
```

```
HTTP/2 200
content-type: text/html
content-length: 704
server: nginx
x-cache: Miss from cloudfront
via: 1.1 <edge>.cloudfront.net (CloudFront)
x-amz-cf-pop: <POP>
x-amz-cf-id: <id>
```

Body: same 704-byte Northline HTML. Not `teamserver-ok`.

### 8. Long-haul `/lh/probe` — valid token **and** allowed UA

```bash
curl -sS -D - \
  -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabCallback/1.0' \
  -H "X-Lab-Token: $TOKEN" \
  "${CLOUDFRONT_LONGHAUL_URL%/}/lh/probe"
```

```
HTTP/2 200
content-type: text/plain; charset=utf-8
content-length: 13
x-cache: Miss from cloudfront
via: 1.1 <edge>.cloudfront.net (CloudFront)
x-amz-cf-pop: <POP>
x-amz-cf-id: <id>

teamserver-ok
```

### 9. Staged binary is not on the decoy URL

OAC can read decoy object keys only. `stage/*` is denied.

```bash
curl -sS -D - "${CLOUDFRONT_URL%/}/stage/sliver-server"
curl -sS -D - "${CLOUDFRONT_LONGHAUL_URL%/}/stage/sliver-server"
```

```
HTTP/2 403
content-type: application/xml
server: AmazonS3
x-cache: Error from cloudfront
via: 1.1 <edge>.cloudfront.net (CloudFront)
x-amz-cf-pop: <POP>
x-amz-cf-id: <id>

<?xml version="1.0" encoding="UTF-8"?>
<Error><Code>AccessDenied</Code><Message>Access Denied</Message></Error>
```

Long-haul: same **403** `AccessDenied`.

### 10. Laptop → redirector EIP (must not serve)

```bash
curl -sS --max-time 8 "http://${PUBLIC_EC2_IP}/"
```

```
curl: (28) Connection timed out after 8038 milliseconds
```

### 11. Same four checks via `make lab-verify`

```bash
PYTHONPATH=src PYTHON=python3 make lab-verify
```

```
ok  decoy
ok  callback without token
ok  scanner user-agent
ok  gated callback
verify ok
```

```bash
PYTHONPATH=src PYTHON=python3 make lab-verify-longhaul
```

```
ok  decoy
ok  callback without token
ok  scanner user-agent
ok  gated callback
verify ok
```

## Status

After apply, load `CLOUDFRONT_URL` / `PUBLIC_EC2_IP` / `TEAMSERVER_IP` from Terraform outputs and run the curls or `make lab-verify`. `make decoy-up` / `make burn-redirector` still **refuse** to apply — you run `terraform apply` yourself.

State is remote S3 (bucket name in gitignored `terraform/config.s3.tfbackend`). CI still runs `terraform init -backend=false`.

## Policy engine

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make test
lab policy validate -f policy/redirector.policy.yaml
lab policy render-nginx \
  -f tests/fixtures/policy.valid.yaml \
  --backend-host 10.42.2.10 \
  --standalone \
  -o generated/nginx-standalone.conf
lab policy test -f tests/fixtures/policy.valid.yaml
```

`policy/redirector.policy.yaml` ships with an **empty** header value on purpose. Render for a real edge needs `--header-value`, `C2_EDGE_HEADER_VALUE`, or Terraform’s generated secret.

## Burn

Redirectors are disposable identities. Burn = **new VM + new EIP**. Terraform updates CloudFront’s nginx origin (EIP reverse-DNS). S3 and the CloudFront hostname stay (that is what implants hit).

```bash
make burn-redirector
# prints, does not apply:
#   terraform -chdir=terraform apply \
#     -replace=aws_instance.redirector \
#     -replace=aws_eip.redirector
```

If `dxxxx.cloudfront.net` is what got blocked, rotating the EIP does nothing. That is a hostname burn (`make burn-hostname` → `-replace=aws_cloudfront_distribution.edge`). Long-haul URL is unchanged.

## BYO C2 (not installed)

This repo does **not** install Sliver, Cobalt Strike, Havoc, or Mythic. Full listener notes: [docs/byo-c2.md](docs/byo-c2.md).

Implants talk to **CloudFront :443**. EC2 is not on the internet except nginx :80 from CloudFront IPs.

| What | Port | Exposed to internet? |
|------|------|----------------------|
| CloudFront | 443 | Yes (callback URL) |
| Redirector nginx | 80 | CloudFront prefix list only |
| SSH | 22 | **No** |
| Teamserver HTTP listener | 8080 | Redirector only (echo until you replace it) |
| CS client 50050 / Sliver 31337 / Havoc 40056 | those | **No** — SSM port-forward to localhost |

Listener **callback host** = that haul’s CloudFront hostname, port **443**. Listener **bind** = HTTP `:8080` on the private box. Profile URIs must stay under `/cdn/` (short) or `/lh/` (long), and must send `X-Lab-Token` plus the LabCallback User-Agent or nginx will serve decoy. Stock Sliver/CS implants fail the gate.

Copy a binary in with `make c2-push FILE=./binary` (S3 `stage/` + SSM). There is no NAT.

## Docs

| File | What |
|------|------|
| [docs/adopt.md](docs/adopt.md) | Inputs, first apply, verify, burn, destroy |
| [docs/byo-c2.md](docs/byo-c2.md) | BYO Sliver/CS/Havoc: ports, copy-in, gate, two hauls, SSM port-forward |
| [docs/categorization.md](docs/categorization.md) | Decoy + PAN/Bluecoat checklist |
| [docs/architecture.md](docs/architecture.md) | Split-origin diagram (two hostnames) |
| [docs/detection.md](docs/detection.md) | What logs/headers exist (not a Sigma pack) |
| [docs/compare.md](docs/compare.md) | vs Lorenzo / Optiv / redStack / C2structor |
| [NON_GOALS.md](NON_GOALS.md) | What this repo will not ship |

## Credits (borrowed pieces)

Filter ideas from [Trizna](https://ditrizna.medium.com/design-and-setup-of-c2-traffic-redirectors-ec3c11bd227d) and [redStack](https://github.com/BaddKharma/redStack). CloudFront origin lock from [Optiv](https://www.optiv.com/insights/discover/blog/redirectors-red-teamers-introduction). SSM-instead-of-SSH from [Red-Formation](https://github.com/scottctaylor12/Red-Formation). Split-origin S3 OAC + policy CLI + EIP burn is this lab’s product.

See [NON_GOALS.md](NON_GOALS.md), [docs/compare.md](docs/compare.md), and [SPEC.md](SPEC.md).
