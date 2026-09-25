import mimetypes
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from apps.tenancy.models import TenantMembership, TenantStatus
from apps.tenancy.services import (
    issue_workspace_session_grant,
    redeem_workspace_session_grant,
)

from .forms import AccountCreationForm, BusinessForm, SignInForm, WorkspaceForm
from .navigation import WORKSPACE_DESTINATIONS, workspace_destination, workspace_launch_url
from .selectors import get_business_profile, get_onboarding_stage, get_owned_workspace
from .services import (
    create_account,
    create_business_profile,
    create_workspace,
    update_account,
    update_workspace,
)

STAGE_URLS = {
    "account": "onboarding:account",
    "workspace": "onboarding:workspace",
    "business": "onboarding:business",
    "ready": "onboarding:ready",
}


def _safe_tenant_destination(request):
    destination = request.POST.get("next") or request.GET.get("next")
    if destination and url_has_allowed_host_and_scheme(
        destination,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return destination
    return reverse("onboarding:workspace_home")


def _stage_redirect(user):
    return redirect(STAGE_URLS[get_onboarding_stage(user)])


def _workspace_url(request, tenant, *, route_name="onboarding:workspace_home"):
    domain = tenant.domains.filter(is_primary=True, is_active=True).first()
    hostname = domain.hostname if domain else f"{tenant.slug}.{settings.TENANT_BASE_DOMAIN}"
    port = request.get_port()
    authority = f"{hostname}:{port}" if port not in {"80", "443"} else hostname
    return f"{request.scheme}://{authority}{reverse(route_name)}"


@require_http_methods(["GET", "POST"])
def account_registration(request):
    if request.user.is_authenticated:
        stage = get_onboarding_stage(request.user)
        is_editing = stage in {"workspace", "business"} and request.GET.get("edit") == "1"
        if not is_editing:
            return _stage_redirect(request.user)
        form = AccountCreationForm(
            request.POST or None,
            user=request.user,
            initial={"first_name": request.user.first_name, "email": request.user.email},
        )
        if request.method == "POST" and form.is_valid():
            user = update_account(user=request.user, **form.cleaned_data)
            if form.cleaned_data["password"]:
                update_session_auth_hash(request, user)
            if stage == "business":
                return redirect(f"{reverse('onboarding:workspace')}?edit=1")
            return redirect("onboarding:workspace")
        return render(
            request,
            "onboarding/account.html",
            {"form": form, "current_step": 1, "is_editing": True},
        )

    form = AccountCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = create_account(**form.cleaned_data)
        login(request, user)
        return redirect("onboarding:workspace")
    return render(request, "onboarding/account.html", {"form": form, "current_step": 1})


@login_required(login_url="/sign-in/")
@require_http_methods(["GET", "POST"])
def workspace_registration(request):
    tenant = get_owned_workspace(request.user)
    is_editing = (
        tenant is not None
        and get_onboarding_stage(request.user) == "business"
        and request.GET.get("edit") == "1"
    )
    if tenant is not None and not is_editing:
        return _stage_redirect(request.user)
    initial = None
    if is_editing:
        initial = {
            "workspace_name": tenant.name,
            "workspace_slug": tenant.slug,
            "timezone": tenant.timezone,
        }
    form = WorkspaceForm(
        request.POST or None,
        request.FILES or None,
        base_domain=settings.TENANT_BASE_DOMAIN,
        tenant=tenant if is_editing else None,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        try:
            if is_editing:
                update_workspace(tenant=tenant, **form.cleaned_data)
            else:
                create_workspace(user=request.user, **form.cleaned_data)
        except IntegrityError:
            form.add_error("workspace_slug", "That workspace URL was just taken.")
        else:
            return redirect("onboarding:business")
    return render(
        request,
        "onboarding/workspace.html",
        {
            "form": form,
            "current_step": 2,
            "display_domain": settings.WORKSPACE_DISPLAY_DOMAIN,
            "is_editing": is_editing,
            "tenant": tenant,
        },
    )


@login_required(login_url="/sign-in/")
@require_GET
def check_workspace_slug(request):
    slug = request.GET.get("workspace_slug", "").strip().lower()
    tenant = get_owned_workspace(request.user)
    if tenant is not None and get_onboarding_stage(request.user) != "business":
        tenant = None
    form = WorkspaceForm(
        {
            "workspace_name": "Workspace",
            "workspace_slug": slug,
            "timezone": "Asia/Manila",
        },
        base_domain=settings.TENANT_BASE_DOMAIN,
        tenant=tenant,
    )
    form.is_valid()
    errors = form.errors.get("workspace_slug", ())
    return render(
        request,
        "onboarding/partials/workspace_slug_feedback.html",
        {
            "available": bool(slug) and not errors,
            "display_domain": settings.WORKSPACE_DISPLAY_DOMAIN,
            "errors": errors,
            "slug": slug,
        },
    )


@login_required(login_url="/sign-in/")
@require_GET
def workspace_logo(request, tenant_id):
    if request.tenant is not None and request.tenant.pk != tenant_id:
        raise Http404("Workspace logo not found.")
    membership = get_object_or_404(
        TenantMembership.objects.select_related("tenant"),
        tenant_id=tenant_id,
        user=request.user,
        is_active=True,
        tenant__status=TenantStatus.ACTIVE,
    )
    logo = membership.tenant.logo
    if not logo:
        raise Http404("Workspace logo not found.")

    try:
        logo_file = logo.open("rb")
    except FileNotFoundError, OSError:
        raise Http404("Workspace logo not found.") from None

    content_type = mimetypes.guess_type(logo.name)[0] or "application/octet-stream"
    response = FileResponse(
        logo_file,
        content_type=content_type,
        as_attachment=False,
        filename=Path(logo.name).name,
    )
    response["Cache-Control"] = "private, max-age=300"
    return response


@login_required(login_url="/sign-in/")
@require_http_methods(["GET", "POST"])
def business_registration(request):
    tenant = get_owned_workspace(request.user)
    if tenant is None:
        return redirect("onboarding:workspace")
    if get_business_profile(tenant) is not None:
        return redirect("onboarding:ready")
    form = BusinessForm(
        request.POST or None,
        initial={
            "legal_name": tenant.name,
            "business_email": request.user.email,
            "currency": "PHP",
            "timezone": tenant.timezone,
        },
    )
    if request.method == "POST" and form.is_valid():
        create_business_profile(tenant=tenant, **form.cleaned_data)
        return redirect("onboarding:ready")
    return render(
        request,
        "onboarding/business.html",
        {
            "form": form,
            "current_step": 3,
            "tenant": tenant,
            "display_domain": settings.WORKSPACE_DISPLAY_DOMAIN,
        },
    )


@login_required(login_url="/sign-in/")
def registration_ready(request):
    tenant = get_owned_workspace(request.user)
    business = get_business_profile(tenant)
    if tenant is None or business is None:
        return _stage_redirect(request.user)
    timezone_labels = dict(BusinessForm.base_fields["timezone"].choices)
    return render(
        request,
        "onboarding/ready.html",
        {
            "current_step": 4,
            "tenant": tenant,
            "business": business,
            "workspace_url": reverse("onboarding:launch_workspace"),
            "product_create_url": workspace_launch_url("add-product"),
            "product_import_url": workspace_launch_url("import-products"),
            "workspace_display_url": f"{tenant.slug}.{settings.WORKSPACE_DISPLAY_DOMAIN}",
            "timezone_label": timezone_labels.get(tenant.timezone, tenant.timezone),
        },
    )


@login_required(login_url="/sign-in/")
@never_cache
@require_GET
def launch_workspace(request):
    tenant = get_owned_workspace(request.user)
    if tenant is None or get_business_profile(tenant) is None:
        return _stage_redirect(request.user)

    grant = issue_workspace_session_grant(tenant=tenant, user=request.user)
    destination = _workspace_url(
        request,
        tenant,
        route_name="onboarding:workspace_session",
    )
    query = {"grant": grant}
    destination_key = request.GET.get("destination", "")
    if destination_key in WORKSPACE_DESTINATIONS:
        query["destination"] = destination_key
    response = redirect(f"{destination}?{urlencode(query)}")
    response["Cache-Control"] = "no-store"
    return response


@never_cache
@require_GET
def workspace_session(request):
    if request.tenant is None:
        raise Http404("Workspace not found.")

    user = redeem_workspace_session_grant(
        tenant=request.tenant,
        token=request.GET.get("grant", ""),
    )
    if user is None:
        return redirect("onboarding:sign_in")

    if not request.user.is_authenticated or request.user.pk != user.pk:
        login(request, user)
    response = redirect(workspace_destination(request.GET.get("destination", "")))
    response["Cache-Control"] = "no-store"
    return response


@never_cache
@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def sign_in(request):
    if request.user.is_authenticated:
        if request.tenant is not None:
            return redirect(_safe_tenant_destination(request))
        return _stage_redirect(request.user)
    form = SignInForm(request.POST or None, request=request, tenant=request.tenant)
    notice = ""
    if request.method == "GET" and request.GET.get("csrf_retry") == "1":
        notice = (
            "Your sign-in form was out of date. Please enter your credentials again. "
            "If this repeats, enable cookies for this site."
        )
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        if request.tenant is not None:
            return redirect(_safe_tenant_destination(request))
        return _stage_redirect(form.get_user())
    return render(
        request,
        "onboarding/sign_in.html",
        {
            "form": form,
            "notice": notice,
            "next": request.POST.get("next") or request.GET.get("next", ""),
        },
    )


@login_required(login_url="/sign-in/")
@never_cache
@require_http_methods(["POST"])
def sign_out(request):
    logout(request)
    response = redirect("onboarding:sign_in")
    response["Cache-Control"] = "no-store"
    return response
