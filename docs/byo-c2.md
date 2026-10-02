# BYO C2 and two hauls

This lab automates the **edge**. It does **not** install Cobalt Strike, Sliver, Havoc, or Mythic. v1’s private EC2 runs a Python echo on `:8080` so `lab verify` works.

Authorized lab only. You own the AWS account.

## Ports — what is actually open

Implant and browsers never talk to EC2. They talk to **CloudFront :443**.

| Path | Port | Who may connect | Notes |
|------|------|-----------------|--------|
| Short-haul CloudFront | **443** | Internet | First callback hostname (`decoy_url`) |
| Long-haul CloudFront | **443** | Internet | Second hostname (`longhaul_url`). Different `dxxxx` |
| Redirector EC2 | **80** | CloudFront origin-facing prefix list only | nginx. Not world-open |
| Redirector EC2 | **22** | Nobody | SSM instead |
| Teamserver EC2 | **8080** (`teamserver_listen_port`) | Redirector SG only | Echo now; your HTTP C2 later |
| Teamserver EC2 | **22** | Nobody | SSM |
| Teamserver → internet | No NAT | — | S3 gateway only. Copy binaries with `make c2-push` |
| Operator C2 GUI | **not in any SG** | You, via SSM port-forward | CS **50050**, Sliver **31337**, Havoc client **40056** (typical). Bind `127.0.0.1` |

Do **not** open 50050 / 31337 / 40056 / 443 on the teamserver to `0.0.0.0/0`. That bypasses the redirector.

TLS map for **this** design:

```text
implant  --HTTPS:443-->  CloudFront  --HTTP:80-->  nginx  --HTTP:8080-->  C2 listener
```

The C2 HTTP listener binds **HTTP** on the private box (default 8080). Do not put an HTTPS listener on 443 on that box unless you change origin TLS (v1 is HTTP origin).

Listener **Host / callback** = the haul’s CloudFront hostname (`dxxxx.cloudfront.net` or your short-haul alias), **port 443**.  
Listener **bind** = `0.0.0.0:8080` (or change `teamserver_listen_port` and re-apply).

## Copy a C2 binary onto the private box

There is **no NAT**. `apt`/`curl` to GitHub will hang. After apply:

```bash
make c2-push FILE=./sliver-server DEST=sliver-server
# laptop → s3://<decoy-bucket>/stage/sliver-server
# SSM RunShellScript → python3 /usr/local/lib/c2-edge-lab/s3_pull.py → /opt/c2/sliver-server
```

`make c2-push` is **not** `terraform apply`. It needs an already-applied stack. Staged objects live under `stage/` and are **not** readable via CloudFront (bucket policy denies OAC on that prefix). They expire after 7 days.

Then SSM onto the teamserver, stop the stub, bind your C2 on the same port:

```bash
aws ssm start-session --target "$(terraform -chdir=terraform output -raw teamserver_instance_id)"
# on the box:
sudo systemctl disable --now c2-edge-echo
sudo chmod +x /opt/c2/sliver-server
```

## Operator GUI (SSM port-forward)

Copy-paste after apply (Session Manager plugin required). Never publish these ports.

Cobalt Strike client **50050**:

```bash
aws ssm start-session \
  --target "$(terraform -chdir=terraform output -raw teamserver_instance_id)" \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["50050"],"localPortNumber":["50050"]}'
```

Sliver multiplayer **31337**:

```bash
aws ssm start-session \
  --target "$(terraform -chdir=terraform output -raw teamserver_instance_id)" \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["31337"],"localPortNumber":["31337"]}'
```

Same commands are Terraform outputs: `ssm_cs_port_forward`, `ssm_sliver_port_forward`.

Point the C2 client at `127.0.0.1`. Havoc’s typical client port is **40056** — same document, change the two numbers.

## Gate vs your profile (this is what people miss)

nginx only `proxy_pass` if **all** of these match `policy/redirector.policy.yaml`:

- Path prefix `/cdn/` (short-haul CloudFront `/cdn/*`) **or** `/lh/` (long-haul CloudFront `/lh/*`)
- Header `X-Lab-Token: <terraform output lab_header_value>`
- User-Agent exactly `Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabCallback/1.0` (or you change the YAML and replace the redirector)

A default Sliver/CS implant will **not** get through. It hits the decoy. Either:

1. Put that header + UA + `/cdn/` (or `/lh/`) prefix on the implant, or  
2. Change the policy to your profile’s URIs / UA / header, `make conf`, replace the redirector instance so user-data ships new nginx.

This repo does **not** import Malleable `.profile` or Sliver `http-c2.json`. Align by hand. Hint for a Sliver HTTP listener (not an import file):

```json
{
  "host": "<cloudfront-hostname>",
  "port": 443,
  "path_prefix": "/cdn/",
  "headers": { "X-Lab-Token": "<lab_header_value>" },
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabCallback/1.0"
}
```

Do **not** disable the header gate in Terraform to make stock implants work.

### Sliver (HTTP)

- On teamserver: `http -L 0.0.0.0 -l 8080` (HTTP, not mTLS).
- Short-haul implant: `https://<short-haul-hostname>/cdn` (path prefix). Port **443** to CloudFront.
- Long-haul implant: `https://<longhaul_url host>/lh` with a **high sleep**. Different hostname.
- mTLS (`:31337`) does not go through this nginx HTTP gate. Don’t use mTLS as the public channel here.
- Operator: port-forward **31337** over SSM if you use multiplayer.

### Cobalt Strike

- Teamserver client: **50050** on localhost via SSM. Never public.
- HTTP Beacon: **Host** = the haul’s CloudFront hostname, beacon port **443**.
- Bind port (HTTP Port Bind) = **8080** (port-bend: 443 out, 8080 on the box). See CS “HTTP Port (Bind)” vs “HTTP Port (C2)”.
- Malleable `Host` header in **both** http-get and http-post = that hostname ([BHIS](https://www.blackhillsinfosec.com/using-cloudfront-to-relay-cobalt-strike-traffic/), [Mudge](https://www.cobaltstrike.com/blog/high-reputation-redirectors-and-domain-fronting)).
- URIs under `/cdn/` (short) or `/lh/` (long). Custom header `X-Lab-Token`. UA must match policy.
- HTTPS Beacon to CloudFront is fine (viewer TLS). Origin to nginx stays HTTP.

### Havoc

- Client port typically **40056** — SSM port-forward, bind locally.
- Listener: `Hosts = ["<cloudfront-hostname>"]`, `PortConn = 443`, `PortBind = 8080`, `HostBind = 0.0.0.0`, `Secure = false` for the **bind** (HTTP to nginx). Agents still use HTTPS to CloudFront.
- `Uris` and `UserAgent` / headers must match the nginx policy.

### Mythic

Same pattern: HTTP listener on **8080** private, agents to CloudFront **443**, GUI via SSM to whatever port you bound (often 7443). Don’t publish 7443.

## Short-haul vs long-haul

[Mudge](https://www.cobaltstrike.com/blog/infrastructure-for-ongoing-red-team-operations) / [Trizna](https://ditrizna.medium.com/design-and-setup-of-c2-traffic-redirectors-ec3c11bd227d): two **hostnames**, so burning one does not kill persistence.

| | Short-haul | Long-haul |
|---|------------|-----------|
| Job | Interactive work, fast callbacks | Persistence, slow (hours), different profile |
| Public identity | `decoy_url` (`edge` distribution) | **Different** `dxxxx` (`longhaul` distribution) |
| CloudFront path | `/cdn/*` | `/lh/*` |
| Sleep | Seconds–minutes | Hours (implant setting, not Terraform) |

Two paths on the **same** `dxxxx.cloudfront.net` are **not** two hauls. This lab mints **two distributions**. Blocking the short-haul hostname does not kill `longhaul_url`.

Still one redirector EIP and one private box (frozen: two EC2s). Identity burn (`make burn-redirector`) updates **both** CloudFront origins. Hostname burn (`make burn-hostname`) replaces only `aws_cloudfront_distribution.edge`. The long-haul `dxxxx` stays.

Sleep and “don’t park all persistence on long-haul” are implant doctrine, not Terraform.

DNS Beacon as long-haul is **out** of this repo (no DNS listener, no 53/udp inbound).

## What this lab is missing (on purpose)

- No C2 install, no profile parser  
- No NAT on the teamserver (`make c2-push` instead)  
- No second redirector/EIP (origin burn still moves both hauls)  
- No DNS/mTLS/SMB redirector  
- No operator GUI port on the internet  
- CloudFront access logs off (see [detection.md](detection.md))  
- Categorization is an operator checklist ([categorization.md](categorization.md)), not a vendor API
