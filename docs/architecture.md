# Architecture

## System shape

IMS v2 is a server-rendered Django modular monolith. Django Templates own presentation, HTMX provides server-driven interactions, Alpine.js handles small client-only state, and PostgreSQL is the system of record.

Each business capability belongs in a focused app under `apps/`. A typical app should evolve toward:

```text
apps/example/
  models/ or models.py    persistence and invariants
  selectors.py            reusable read queries
  services.py             transactional workflows
  forms.py                input validation
  views.py                HTTP orchestration
  urls.py                 routes
  templates/example/      full templates and partials
  tests/                   behavior and isolation tests
```

Use a package (`models/`, `views/`, or `services/`) when a module develops multiple responsibilities. Do not split files merely to satisfy a pattern.

Shared interface elements live under `templates/components/`, with their component-level styles in the Tailwind component layer. Feature templates compose these components and must not fork their visual rules. This keeps interaction patterns and appearance uniform as the application grows.

## Tenant model

The initial tenancy strategy is shared database/shared schema with explicit tenant foreign keys:

- `Tenant` is the organization boundary.
- `TenantDomain` maps an exact host to one tenant.
- `TenantMembership` authorizes a user within a tenant.
- `TenantOwnedModel` adds the tenant key and a fail-closed default manager.
- Middleware resolves the host, establishes the request context, and verifies membership.

Tenant context narrows queries; it is not a substitute for authorization. Services must also check the user's role/capability. Cross-tenant reporting and maintenance must use deliberately named infrastructure paths and the unscoped manager under review.

## Request flow

1. Django validates the host against `ALLOWED_HOSTS`.
2. `TenantResolutionMiddleware` resolves an active exact domain and establishes a context-local tenant.
3. Django authentication resolves the user.
4. `TenantAccessMiddleware` denies authenticated users without an active membership.
5. Views call selectors/services; tenant-owned default managers automatically constrain reads and writes.
