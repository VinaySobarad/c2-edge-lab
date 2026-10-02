# Detection notes

Thin notes on **what exists in this lab**. Not a Sigma pack. Not CloudFront access logging (that is off in v1).

## What a viewer sees

TLS and the Host header are the **CloudFront hostname** (`dxxxx.cloudfront.net` or your alias). They do not see the redirector EIP. The EIP only accepts CloudFront origin-facing IPs (`com.amazonaws.global.cloudfront.origin-facing`). A laptop `curl` to `http://EIP/` must fail.

CloudFront adds these on the **response** (and often on the forwarded request):

| Header | Meaning |
|--------|---------|
| `via` | Shows CloudFront in the chain |
| `x-amz-cf-id` | Per-request id |
| `x-amz-cf-pop` | Edge POP |

`curl -sSI https://<decoy_url>/` is enough to see them. They are not proof of C2; they are proof the edge is CloudFront.

## nginx (origin)

Policy compiles to three `map`s, not `if` + `proxy_pass`:

- header token → `$c2e_header_ok`
- User-Agent → `$c2e_ua_class` (`allow` / `scanner` / `other`)
- combined → `$c2e_gate` (`proxy` or `decoy`)

Gated paths (`/cdn/`, `/lh/`) return 418/419 internally and land on named locations `@proxy` or `@decoy`. Failed ordered paths **cannot** fall back to S3; CloudFront already chose the nginx origin.

The site conf does not set `access_log off`. Default combined logs go to `/var/log/nginx/access.log` on the redirector (read via SSM). Expect CloudFront edge IPs as `$remote_addr`, not the implant. Real client IP is in `X-Forwarded-For` if AllViewer forwarded it.

v1 ships no CloudFront standard logging bucket.

## Short detection ideas

- Same process talking on a schedule to one unused `*.cloudfront.net` (or a young custom alias) with POSTs on `/cdn/*`.
- Requests to `/cdn/*` that always send a custom header (`X-Lab-Token` here) plus a rare exact User-Agent.
- Scanners (`curl`, `sqlmap`, …) always getting the same decoy HTML; only the profile-shaped client getting a different body.
- Origin EIP in passive DNS / cert / error pages — then probes from non-CloudFront IPs should be **refused** by the SG. If they are not, the prefix list is broken.

Do not treat “traffic to CloudFront” as malicious by itself. Blocking all CloudFront breaks a lot of the internet.
