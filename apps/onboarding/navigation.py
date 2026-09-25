from django.urls import reverse

WORKSPACE_DESTINATIONS = {
    "products": "inventory:product_list",
    "add-product": "inventory:product_create",
    "import-products": "inventory:product_import",
}


def workspace_destination(key):
    """Only allow known workspace routes through the cross-host session handoff."""
    return reverse(WORKSPACE_DESTINATIONS.get(key, "onboarding:workspace_home"))


def workspace_launch_url(key):
    if key not in WORKSPACE_DESTINATIONS:
        return reverse("onboarding:launch_workspace")
    return f"{reverse('onboarding:launch_workspace')}?destination={key}"
