# Local development runbook

This runbook mirrors the local workflow used by the neighboring ClinicSuite project while keeping IMS v2 isolated in its own database.

## Requirements

- Python 3.14+
- Node.js 20+
- PostgreSQL 14+ (the local Postgres.app instance is supported)

## First-time setup

1. Start Postgres.app and confirm it is ready:

   ```bash
   pg_isready
   ```

2. Create and activate the Python environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements-dev.txt
   ```

3. Configure the application:

   ```bash
   cp .env.example .env
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

   Put the generated value in `DJANGO_SECRET_KEY` and use the PostgreSQL credentials configured for your local server in `DATABASE_URL`.

4. Install and build frontend assets:

   ```bash
   npm install
   npm run build
   ```

5. Initialize the schema and verify the installation. The local `ims_v2` database was created during project bootstrap; `migrate` also confirms that the configured credentials can access it:

   ```bash
   python manage.py migrate
   python manage.py check
   pytest
   ```

6. Create the first tenant and optional user membership:

   ```bash
   python manage.py create_tenant "Example Company" example.localhost
   python manage.py createsuperuser
   python manage.py add_tenant_member example.localhost admin@example.com owner
   ```

7. Run the development processes in separate terminals:

   ```bash
   npm run dev
   python manage.py runserver
   ```

## Useful commands

```bash
ruff check .
ruff format --check .
pytest
python manage.py makemigrations --check --dry-run
python manage.py check --deploy --settings=config.settings.prod
```

## Tenant debugging

- Tenant identity comes from an exact active `TenantDomain.hostname` match.
- Use `example.localhost:8000`, not a request parameter or arbitrary header.
- A signed-in user also needs an active `TenantMembership` for that tenant.
- Tenant-owned models fail closed when their default manager is used without an active tenant context.

## Data handling

- Do not delete or rewrite existing data unless explicitly requested.
- Back up the database before deployments or destructive schema/data work.
- Prefer additive migrations and reversible operations.
- Keep test fixtures tenant-scoped and minimal.
