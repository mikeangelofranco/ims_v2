# CoreFlow / IMS v2

CoreFlow is a security-conscious, multi-tenant inventory management platform built with Django Templates, Tailwind CSS, HTMX, Alpine.js, and PostgreSQL.

The repository currently contains platform scaffolding only; no product pages have been implemented.

## Start here

Follow [RUNBOOK.md](RUNBOOK.md) for local setup and common commands. Read [Architecture](docs/architecture.md), [Security](docs/security.md), and [Design system](docs/design-system.md) before adding features.

## Top-level structure

```text
apps/
  accounts/       Custom identity model
  common/         Shared abstract models and utilities
  tenancy/        Tenant, domain, membership, context, and isolation
config/
  settings/       Environment-specific Django settings
docs/             Architecture, security, and design decisions
static/src/       Tailwind source and JavaScript entry point
templates/        Project-level templates and reusable components
```

