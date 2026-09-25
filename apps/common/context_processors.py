from .assets import asset_version


def application(request):
    return {"asset_version": asset_version()}
