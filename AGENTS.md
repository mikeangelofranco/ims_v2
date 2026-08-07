# CoreFlow/IMS v2 engineering rules

These constraints apply to every change in this repository.

## Required stack

- Django and Django Templates
- Tailwind CSS
- HTMX
- Alpine.js (the CSP-compatible build)
- PostgreSQL

Do not introduce a frontend SPA framework or a second persistence layer without an explicit architecture decision.

## Architecture

- Keep domain code in focused Django apps under `apps/`.
- Keep settings and deployment wiring in `config/`; shared infrastructure belongs in `apps/common/`.
- Keep views thin. Put reusable business workflows in `services.py`, query composition in `selectors.py`, validation in forms/models, and presentation in templates/components.
- Split files when responsibilities diverge. Do not accumulate unrelated models, views, services, or templates in one file.
- Prefer reusable template partials and components over copied markup.
- Add tests with each behavior change.

## Multi-tenancy and security

- This is a shared-database, shared-schema multi-tenant system.
- Every tenant-owned model must inherit `apps.tenancy.models.TenantOwnedModel`.
- Use its scoped `objects` manager in request and business code. `all_objects` bypasses tenant isolation and is reserved for narrowly reviewed infrastructure, administration, migrations, and cross-tenant jobs.
- Never accept a tenant identifier from normal request data as authorization. Resolve the tenant from the validated host and verify an active membership.
- Tenant uniqueness must include `tenant`, and tenant relationships must be validated to prevent cross-tenant references.
- Default to deny, least privilege, CSRF protection, output escaping, parameterized ORM queries, and local static assets.
- Never log secrets, credentials, session identifiers, or sensitive business records.
- Destructive data operations require an explicit request and a recoverable backup.

## Design system

- Use only the semantic tokens in `tailwind.config.js` and `static/src/app.css`; do not place ad-hoc hex colors in templates or feature CSS.
- Every recurring interface element must use a shared component or an approved component variant. This includes buttons, links, inputs, selects, text areas, checkboxes, tables, cards, badges, alerts, tabs, pagination, dropdowns, dialogs, empty states, and navigation.
- Feature templates may compose shared elements but must not redefine their typography, spacing, radius, borders, focus states, disabled states, or interaction behavior locally.
- A new visual variant must represent a reusable semantic purpose, be added to the shared component layer, and include all relevant states (default, hover, focus-visible, active, disabled, loading, invalid, and read-only where applicable).
- Prefer a small, intentional set of variants over page-specific styling. Similar actions must look and behave the same throughout the product.
- Accessibility is part of component consistency: preserve semantic HTML, keyboard behavior, visible focus, labels, error associations, and sufficient contrast.
- Primary: `#2563EB`; hover: `#1D4ED8`; active: `#1E40AF`.
- Success: `#16A34A`; warning: `#F59E0B`; danger: `#DC2626`; info: `#0891B2`.
- Text: `#0F172A`, `#475569`, `#94A3B8`.
- Surfaces/borders: `#F8FAFC`, `#FFFFFF`, `#E2E8F0`, `#CBD5E1`, `#E5E7EB`.
- Accent gradients: `#2563EB` to `#1D4ED8`, and `#0891B2` to `#0EA5E9`.
- Use Inter, 12px default radius, Lucide icons, and the defined subtle/elevated shadows.
