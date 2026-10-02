# Comparison — what we borrowed vs what we ship

Pieces are borrowed. The product is the combination. We do not clone these repos.

| | This lab | [Lorenzo](https://lorenzomeacci.com/creating-a-c2-infrastructure-on-aws) | [Optiv](https://www.optiv.com/insights/discover/blog/redirectors-red-teamers-introduction) | [redStack](https://github.com/BaddKharma/redStack) | [C2structor](https://github.com/optionalCTF/C2structor) |
|---|----------|---------|-------|----------|------------|
| Public edge | CloudFront split origin | Direct EC2 / Route 53 | CloudFront **one** origin (Apache) | No CloudFront | CloudFront + Caddy |
| Decoy | Private **S3 OAC** for `/*` | Operator site on Apache | Not S3 | HTML on Apache disk | Not S3 split |
| Filters | Policy YAML → nginx maps (header, URI, UA) | Manual | Left as next step | Header + URI + scanner block | Caddy |
| Teamserver | Private EC2, **BYO** | SSH `-R`, optional Havoc | Separate CS box | Mythic/Sliver/Adaptix **installed** | Optional Havoc |
| Admin | **SSM, no port 22** | SSH | SSH | SSH / Guacamole | SSH |
| Origin lock | CloudFront prefix list on :80 | N/A | Prefix list | N/A | Operator |
| Burn | New VM **+ new EIP**; CF origin follows; hostname stays | Rebuild by hand | New redirector | Rebuild stack | Rebuild |
| Installs C2 | **No** | Operator | No (profile only) | **Yes** | Optional |

Also credited, not cloned: [Trizna](https://ditrizna.medium.com/design-and-setup-of-c2-traffic-redirectors-ec3c11bd227d) (nginx, UA, decoy, haul/burn ideas), [bluescreenofjeff](https://bluescreenofjeff.com/2016-06-28-cobalt-strike-http-c2-redirectors-with-apache-mod_rewrite/) (URI + UA gate), [Red-Formation](https://github.com/scottctaylor12/Red-Formation) (SSM instead of SSH), [Red-Terroir](https://github.com/b3n-j4m1n/Red-Terroir) / [RastaMouse](https://rastamouse.me/infrastructure-as-code-terraform-ansible/) (Terraform rebuild of burned redirectors).

**Out of this repo on purpose:** Cloudflare Workers ([cgomezsec](https://cgomezsec.com/blog/securing-c2-for-rt-operations-using-cloudflare)), Packer AMIs (WolfPack), Cobalt profile parsers (Malleable-Redirector / cs2modrewrite), smtp/phishing boxes.

**Ours:** two hostnames each split S3 decoy vs gated nginx; `lab` policy CLI with tests; identity burn that updates the CloudFront origin and leaves callback hostnames alone; hostname burn that replaces only the short-haul distribution.
