# Security policy — Project Sycamore (baseline)

Non-negotiables for every phase. Exceptions require a logged entry in `DECISIONS.md` with rationale and sunset condition. Review at each gate transition; full re-audit before G3 launch and again after any feature that adds an attack surface (accounts, payments, webhooks).

## 1. Edge & transport

- All public traffic through Cloudflare: managed WAF ruleset on, bot fight mode for known scrapers/bots, rate limiting tuned per route, HSTS preload enabled, TLS ≥ 1.2 with modern cipher defaults, OCSP stapling.
- Security headers on every response (enforced in CI check): strict `Content-Security-Policy` (no inline scripts; third-party domains explicitly allowlisted), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` minimal, frame-ancestors locked.
- No public application server at launch — the edge serves a static bundle only. Any later backend sits behind auth + WAF and is never directly exposed from this host's IP range (Cloudflare proxy mode mandatory).

## 2. Ingest service (the one dynamic component)

- Runs on this laptop as a non-root user under systemd with restart-on-failure; no network access except an egress allowlist of the data-source domains it needs.
- Pinned dependencies + lockfile; dependency audit in CI (`npm audit` / `pip-audit`) — high-severity findings block deploy until fixed or explicitly waived (logged).
- Secrets loaded from `_private/runtime.env` (chmod 600, dir chmod 700) via systemd env-file. Never in the repo, logs, headers, or client bundle. Rotate on a schedule and after any suspected exposure.

## 3. Accounts & data (G4+ only until then)

- No accounts, no PII, no cookies beyond functional ones before G4. Analytics at launch: privacy-respecting self-hosted counter (e.g., Umami) or none — decision logged when chosen.
- When auth is added: managed provider preferred; if self-hosted, MFA enforced on all admin/operator surfaces, password policy + breach-list check, session tokens short-lived with rotation. Payment data never touches our servers (merchant of record handles card data).

## 4. Content & legal hygiene

- Third-party news content: store headline/summary + link out; do not mirror full articles (copyright exposure). Every feed item links to its primary source.
- Privacy policy and terms published before G3 launch, even if minimal at first.
- No deceptive tracking or dark patterns — brand credibility is the product.

## 5. Monitoring & incident response

- External uptime check from off-host; ingest-health endpoint checked by the same monitor (staleness alerting: data older than threshold → page Lord Yams via approved channel).
- Security header scan + dependency audit run in CI on every deploy artifact, not just code pushes.
- Kill switch procedure documented before launch: Cloudflare pause / DNS cut isolates the site from this host's compromise; SQLite DB nightly backup with off-site copy added at G3.

## 6. Local-host hygiene (this machine is public-facing now)

- The always-on laptop hosts ingest + build only — no other long-lived listening services on reachable ports without a logged justification.
- OS/dependency updates scheduled automatically; unattended-upgrades enabled for security patches where the distro supports it safely.
