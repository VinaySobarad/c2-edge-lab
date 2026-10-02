# Categorization — make the decoy look like a site

The decoy is what scanners and URL filters see on `/`. A thin `index.html` is a tell. This lab now ships `app.css`, `app.js`, `favicon.svg`, and `robots.txt`. That is still **not** a real marketing site.

Authorized lab only. You own the domain (or the `dxxxx.cloudfront.net` hostname).

## Why this exists

PAN URL Filtering, Symantec/Blue Coat, Cisco Umbrella, and similar products classify a hostname. A new CloudFront URL is often **unknown / newly registered / computer-and-internet-info**. Callbacks from a categorized “news / business / content delivery” host survive longer than a raw IP.

This repo does **not** submit your lab hostname to vendors for you. That is an operator checklist.

## Operator checklist (docs, not Terraform)

Do this **after** apply, against the **short-haul** URL first (`terraform output decoy_url`), then the **long-haul** (`terraform output longhaul_url`). Two hostnames should not share one category ticket if you want independent burn.

1. Open `/` in a normal browser. Confirm HTML + CSS + favicon. No login form.
2. `curl -sI https://<host>/robots.txt` — 200, `User-agent`.
3. `curl -sI https://<host>/favicon.svg` — 200, `image/svg+xml`.
4. Wait for CloudFront cache (default `/*` is CachingOptimized).
5. **Palo Alto / PAN-DB:** submit the hostname via the PAN URL-filtering submit form (or a lab PAN-DB cloud lookup). Aim for a benign category (business, computer-and-internet-info). Do not aim for “command-and-control”.
6. **Symantec / Blue Coat WebPulse:** submit the URL. Same goal: content-delivery / business, not uncategorized forever.
7. **Cisco Umbrella / OpenDNS:** check the domain reputation page.
8. Re-check after 24–48 hours. New `dxxxx.cloudfront.net` names often stay unknown; a custom domain you have aged is stronger.
9. After **hostname burn** (`make burn-hostname`), the short-haul `dxxxx` is new — recategorize. Long-haul URL is unchanged.

## What this lab will not do

- No parked-domain / expired-domain shopping
- No paying a categorization vendor from Terraform
- No fake login pages (phishing is out of this repo)
- No claiming the decoy will pass every proxy on day one
