from django.urls import path

from . import catalog_views, detail_views, movement_views, report_views, views

app_name = "inventory"
urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("categories/", catalog_views.category_list, name="category_list"),
    path("categories/new/", catalog_views.category_create, name="category_create"),
    path("categories/<uuid:pk>/edit/", catalog_views.category_edit, name="category_edit"),
    path("categories/<uuid:pk>/status/", catalog_views.category_status, name="category_status"),
    path("movements/", movement_views.movement_list, name="movement_list"),
    path("movements/export/", movement_views.movement_export, name="movement_export"),
    path("reports/", report_views.report_list, name="report_list"),
    path("reports/export/", report_views.report_export, name="report_export"),
    path("fields/", catalog_views.custom_fields, name="custom_fields"),
    path("fields/new/", catalog_views.custom_field_create, name="custom_field_create"),
    path("new/", views.product_create, name="product_create"),
    path("export/", views.product_export, name="product_export"),
    path("import/", views.product_import, name="product_import"),
    path("<uuid:pk>/image/", views.product_image, name="product_image"),
    path(
        "<uuid:pk>/images/<uuid:image_pk>/",
        detail_views.product_gallery_image,
        name="product_gallery_image",
    ),
    path("<uuid:pk>/", detail_views.product_detail, name="product_detail"),
    path("<uuid:pk>/label/", detail_views.product_label, name="product_label"),
    path("<uuid:pk>/duplicate/", detail_views.product_duplicate, name="product_duplicate"),
    path("<uuid:pk>/archive/", detail_views.product_archive, name="product_archive"),
    path("<uuid:pk>/gallery/", detail_views.product_gallery_upload, name="product_gallery_upload"),
    path(
        "<uuid:pk>/stock/<str:kind>/",
        detail_views.product_stock_action,
        name="product_stock_action",
    ),
    path("<uuid:pk>/edit/", views.product_edit, name="product_edit"),
]
