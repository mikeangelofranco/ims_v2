import os

from django.test import override_settings

from apps.common.context_processors import application


def test_development_cache_version_changes_for_either_bundle(tmp_path):
    css = tmp_path / "static/css/app.css"
    js = tmp_path / "static/js/app.js"
    for file in (css, js):
        file.parent.mkdir(parents=True)
        file.write_text("initial")
    with override_settings(DEBUG=True, BASE_DIR=tmp_path):
        initial = application(None)["asset_version"]
        assert initial == application(None)["asset_version"]
        css.write_text("updated CSS")
        os.utime(css, ns=(css.stat().st_atime_ns, css.stat().st_mtime_ns + 1_000_000))
        after_css = application(None)["asset_version"]
        assert after_css != initial
        js.write_text("updated JS")
        os.utime(js, ns=(js.stat().st_atime_ns, js.stat().st_mtime_ns + 1_000_000))
        assert application(None)["asset_version"] != after_css


def test_production_cache_version_remains_release_version(tmp_path):
    with override_settings(DEBUG=False, BASE_DIR=tmp_path, ASSET_VERSION="release-123"):
        assert application(None)["asset_version"] == "release-123"


def test_development_without_bundles_can_render(tmp_path):
    with override_settings(DEBUG=True, BASE_DIR=tmp_path):
        assert application(None)["asset_version"]
