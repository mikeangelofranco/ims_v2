# Security baseline

- Production settings fail if secrets, hosts, trusted origins, or PostgreSQL configuration are absent.
- Cookies are HTTP-only, secure in production, and use `SameSite=Lax`.
- HTTPS redirect, HSTS, content sniffing protection, referrer policy, clickjacking protection, and a restrictive Content Security Policy are enabled in production.
- Alpine uses its CSP-compatible build; JavaScript and CSS are bundled locally.
- Argon2 is the preferred password hasher.
- Authentication uses a custom email-based user model established before the first migration.
- Tenant resolution uses the validated host. Unknown/inactive domains return 404; authenticated users without membership receive 403.
- Tenant-owned querysets fail closed outside tenant context.

Application-layer tenant scoping must be reinforced with tests for every feature. Before handling highly sensitive or regulated data, evaluate PostgreSQL row-level security as an additional control; it requires transaction-local tenant state and dedicated operational handling, so it must be introduced as a reviewed architecture change rather than a partial toggle.

