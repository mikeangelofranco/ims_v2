import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_landing_page_is_public(client):
    response = client.get(reverse("marketing:landing"))

    assert response.status_code == 200
    assert b"The core of your business" in response.content
    assert b"Start Free Trial" in response.content
    assert b'class="dashboard-shell"' in response.content
    assert b"app-dashboard-shell" not in response.content
