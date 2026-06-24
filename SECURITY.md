# Security

## Reporting a vulnerability

We take security seriously. If you find a vulnerability in Ethical Panel, please report it privately:

- **Open a GitHub Security Advisory**: <https://github.com/RegeneratusLabs/ethicalpanel/security/advisories/new> (preferred — keeps it private until patched)
- **Do not** open a public issue for security bugs

We'll acknowledge within 48 hours and aim to ship a fix within 7 days for critical issues, 30 days for everything else.

## What counts as a vulnerability

- Anything that lets an unauthenticated user read or write data they shouldn't
- Prompt injection that causes the agents to behave in ways the operator didn't intend
- Rate-limit bypasses
- XSS, CSRF, SSRF, RCE, SQLi, etc.
- Anything that leaks the origin VPS IP (we use a Cloudflare Tunnel specifically to keep this hidden)

## Out of scope

- "I disagree with an agent's verdict" — the agents are AI; their outputs are opinions, not facts. Open a regular issue with the `enhancement` label.
- Rate-limiting the live site aggressively — we already have per-IP limits in the app and CF WAF. If you need a higher limit, talk to us.
- The DeepSeek API itself — report those bugs to DeepSeek, not us.

## Hardening notes (for self-hosters)

If you're running your own instance, the `deploy/` directory has:

- A hardened systemd unit (`ProtectSystem=strict`, `ProtectHome=read-only`, etc.) — `systemd-analyze security ethical-panel` should report around 5.0 MEDIUM
- A Caddyfile with HSTS, strict CSP, no external resources
- UFW + fail2ban + unattended-upgrades enabled by the bootstrap script
- Cloudflare Tunnel (not direct origin exposure)

Don't run this on a VPS that has ports other than 22/80/443 open to the public internet, and don't point DNS directly at the VPS IP.
