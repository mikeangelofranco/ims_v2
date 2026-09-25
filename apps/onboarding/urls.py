from django.urls import path

from apps.dashboard import views as dashboard_views

from . import views

app_name = "onboarding"

urlpatterns = [
    path(
        "workspace-logo/<uuid:tenant_id>/",
        views.workspace_logo,
        name="workspace_logo",
    ),
    path("register/", views.account_registration, name="account"),
    path("register/workspace/", views.workspace_registration, name="workspace"),
    path(
        "register/workspace/check-slug/",
        views.check_workspace_slug,
        name="check_workspace_slug",
    ),
    path("register/business/", views.business_registration, name="business"),
    path("register/ready/", views.registration_ready, name="ready"),
    path("launch-workspace/", views.launch_workspace, name="launch_workspace"),
    path("sign-in/", views.sign_in, name="sign_in"),
    path("logout/", views.sign_out, name="sign_out"),
    path("app/session/", views.workspace_session, name="workspace_session"),
    path("app/", dashboard_views.dashboard, name="workspace_home"),
]
