# Products

The tenant workspace Products navigation opens `/app/products/`.

Inventory code lives in `apps/inventory/`: models and migrations define persistence,
forms validate request input, selectors compose tenant-scoped inventory queries,
services save products and record opening stock, and `csv_io.py` handles CSV files.
Views coordinate these layers. Templates compose shared components in
`templates/components/`; shared workspace component styles live in
`static/src/workspace.css`, imported by the Tailwind entry point.

## Behavior

- Search product names, SKUs, barcodes, and category names. Enter submits search;
  Command/Ctrl K focuses the search field.
- Status tabs and category filters preserve query state. Sortable columns and
  pagination operate on the filtered database query. Page sizes are 10/25/50/100.
- Stock and minimum stock are totals across locations. Active products at zero
  stock are out of stock; positive quantities at or below the minimum are low
  stock. Inactive products have their own status. The all-products total includes
  inactive products. Summary counts cover the workspace, independently of filters.
- Owners, administrators, and members can add/edit/import products. Viewers can
  list and export. Validated host resolution and active membership are required.
- Opening quantities are recorded as stock receipts with an actor and ledger
  balance. Editing product metadata does not rewrite stock balances.
- Selling price is independent of unit cost. Existing prices start at zero; costs
  are preserved. Product images are optional PNG/JPG files, limited to 5 MB and
  retrieved through a tenant-scoped authenticated endpoint.
- Checkboxes select the current page for export. Without a selection, export
  includes all matching products. CSV text cells are escaped for spreadsheet
  formula safety.
- CSV import creates up to 1,000 new products (2 MB file maximum). Required
  headers: `name,sku`. Optional headers: `description,barcode,selling_price,
  unit_cost,is_active`. Import does not alter existing products, categories, or
  stock. Invalid rows roll back the whole import. Reimporting exported existing
  SKUs is rejected rather than overwriting records.

## Validation

Run `npm run build`, `python manage.py migrate`, `python manage.py check`, and
`pytest`. Product behavior tests are in `apps/inventory/tests/test_products.py`.
The desktop layout was inspected at the reference's 1536 × 1024 dimensions using
transactionally rolled-back preview records; no demonstration inventory was seeded.

## Mobile layout

Below 900px, product rows become cards with thumbnails, descriptions, SKU/category,
stock/minimum, status, price, and a shared action menu. Mobile navigation stays at
bottom and Products remains active. Summary cards and scrollable status tabs use
workspace counts. The mockup's sample growth and notification badges are not
rendered because those features have no data source yet.

Mobile search, filter and sorting controls use the same scoped selectors. The
location filter restricts products and their stock/minimum totals to that location.
It does not change workspace summary counts. Six cards load per batch; HTMX appends
subsequent batches without replacing existing cards. Without JavaScript, the link
opens the next page. Search/filter/sort changes reset the mobile batch sequence.
Desktop pagination continues using its chosen page size.

## Add Product

Dashboard quick actions, product-list Add Product buttons, and onboarding links
open `/app/products/new/` on the validated workspace host. The desktop editor
composes shared form, upload, switch, dialog, card, and button components; its
styles are in `static/src/forms.css`.

Name, category, and selling price are required. An omitted SKU is generated;
SKU/barcode uniqueness is scoped to the tenant. Optional fields include a
500-character description, brand, model, image, cost, unit of measure, and the
Has Variants setting. The setting is stored for later variant configuration;
this page does not create separate variant SKUs or balances.

Opening stock and minimum stock use whole units. With one active location it is
selected automatically. Multiple active locations expose a location selector;
a workspace without one receives a Main Warehouse. Product creation, custom
values, initial stock level, and the opening receipt save in one transaction.
Disabling tracking requires zero opening/minimum quantities and excludes the
product from stock alerts. Save & Add Another opens a fresh form after saving.

Members can create tenant categories inline. Owners and administrators can
create reusable optional text fields inline and enable/disable them at
`/app/products/fields/`. Disabling a field retains saved values. HTMX dialog
updates preserve unsaved product input, with regular page fallbacks available.
All related category/location/field selections use scoped queries; foreign
references and unauthorized roles are rejected.

Additional creation behavior tests are in `test_add_product.py`.

## Mobile Add Product

Below 900px, the Add Product editor uses compact cards. Basic Information starts
open; Pricing, Inventory, Product Options, and Additional Information can be
expanded with keyboard-accessible buttons. Server and browser validation opens
the section containing an invalid field. Without JavaScript, every field stays
visible. The form keeps one Save Product action and a fixed Cancel/Save bar;
Save & Add Another remains available on desktop. The same tenant-scoped form and
save workflow handle both layouts.

`npm run dev` now watches CSS, HTML, and JavaScript sources. Each change runs a
fresh Tailwind CSS build; esbuild also watches JavaScript. Production assets are
built with `npm run build`.

## Product detail (desktop)

Selecting a product name or thumbnail in the product list—including filtered
search results—opens `/app/products/<id>/`. Dashboard low-stock View links and
stock-activity product links open the same tenant-scoped page. Viewers can read
it; product editors can use its actions.

The page uses stored product fields, the primary image and up to eight additional
PNG/JPG gallery images, custom-field values, stock levels by location, five recent
stock movements, and a 30-day receipt/issue/adjustment summary. Percentages and
totals are computed from location balances. Movement references use the stable
movement ID. Additional images have tenant-scoped authenticated URLs.

Receive, adjust, and transfer forms validate active locations and record atomic
ledger movements with the actor. Transfers create linked outgoing and incoming
movements and roll back when the source lacks stock. Duplicate copies product
metadata and custom values into an inactive item with a new SKU, no barcode, and
no stock. Archive changes status and can be reversed by Reactivate; it does not
delete records. Print Label opens a print-ready page with the product name, SKU,
and barcode text. The activity table records new metadata, image, status, and
stock changes, with paginated View all. Events before this activity feature was
added cannot be reconstructed from existing product metadata.

The validated workspace host and active membership control every detail and
media route. All product, image, stock, movement, and custom-field queries use
tenant-scoped managers. Tests are in `test_product_detail.py`.
