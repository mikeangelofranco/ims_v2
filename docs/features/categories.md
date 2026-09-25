# Categories

Categories organize products within the current workspace. Each category has a tenant-unique name,
slug, and code, plus an optional description and Lucide icon. Deactivating a category preserves its
existing product assignments while removing it from new-product category choices.

The category list is tenant-scoped and supports search, status filtering, sorting, and pagination.
Product totals use the existing `Product.category` relationship. The uncategorized total includes
only products in the current tenant.

Owners, administrators, and members can create, edit, activate, and deactivate categories. Viewers
can read the list. Category routes resolve records with the tenant-scoped manager, so identifiers
from another workspace return `404`.
