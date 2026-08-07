from django.conf import settings


def application(request):
    return {"asset_version": settings.ASSET_VERSION}
