"""Creating and editing apps, and the migration that added an app's own auth
method. Set TEST_DATABASE_URL to run. An auth method change recorded on the
app's open exposure is in test_exposures."""
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from api.models import CreateAppRequest, PatchAppRequest
from api.routes_apps import create_app, list_apps, patch_app
from core.db import AppRow

from .conftest import REPO_ROOT

# The revision before the one that added apps.auth_method.
BEFORE_AUTH_METHOD = "f1c3e5a7b9d2"


def _request(factory) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(session_factory=factory)))


def _alembic(db_url: str, *args: str) -> None:
    r = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT, env={**os.environ, "DATABASE_URL": db_url}, capture_output=True, text=True,
    )
    assert r.returncode == 0, f"alembic {' '.join(args)} failed:\n{r.stdout}{r.stderr}"


async def test_an_app_is_created_with_its_auth_method(factory):
    body = CreateAppRequest(name="Payroll", url="https://payroll.corp.internal", owner_ad_group="g", auth_method="kerberos")
    created = await create_app(body, _request(factory))
    assert created.auth_method == "kerberos"

    async with factory() as session:
        assert (await session.get(AppRow, created.id)).auth_method == "kerberos"
    [listed] = await list_apps(_request(factory))
    assert listed.auth_method == "kerberos"


async def test_existing_apps_are_backfilled_as_oauth(factory, migrated_db):
    # factory has emptied the tables. Step back to before the column, add an
    # app the way that schema would have, and upgrade again.
    _alembic(migrated_db, "downgrade", BEFORE_AUTH_METHOD)
    try:
        async with factory() as session:
            await session.execute(text(
                "INSERT INTO apps (id, name, url, owner_ad_group, created_at) "
                "VALUES ('app_old', 'Old', 'https://old.corp.internal', 'g', now())"
            ))
            await session.commit()
    finally:
        _alembic(migrated_db, "upgrade", "head")

    async with factory() as session:
        assert (await session.get(AppRow, "app_old")).auth_method == "oauth"
        # No default survives the backfill: an insert that names no method fails.
        with pytest.raises(Exception, match="auth_method"):
            await session.execute(text(
                "INSERT INTO apps (id, name, url, owner_ad_group, created_at) "
                "VALUES ('app_new', 'New', 'https://new.corp.internal', 'g', now())"
            ))


async def _payroll(factory) -> str:
    body = CreateAppRequest(name="Payroll", url="https://payroll.corp.internal", owner_ad_group="g", auth_method="oauth")
    return (await create_app(body, _request(factory))).id


async def test_patch_changes_only_the_fields_it_names(factory):
    app_id = await _payroll(factory)

    renamed = await patch_app(app_id, PatchAppRequest(name="Payroll 2"), _request(factory))
    assert (renamed.name, renamed.owner_ad_group, renamed.auth_method) == ("Payroll 2", "g", "oauth")

    changed = await patch_app(
        app_id, PatchAppRequest(owner_ad_group="finance", auth_method="kerberos"), _request(factory)
    )
    assert (changed.name, changed.owner_ad_group, changed.auth_method) == ("Payroll 2", "finance", "kerberos")
    assert changed.url == "https://payroll.corp.internal"

    async with factory() as session:
        row = await session.get(AppRow, app_id)
        assert (row.name, row.owner_ad_group, row.auth_method) == ("Payroll 2", "finance", "kerberos")


async def test_an_empty_patch_changes_nothing(factory):
    app_id = await _payroll(factory)
    unchanged = await patch_app(app_id, PatchAppRequest(), _request(factory))
    assert (unchanged.name, unchanged.owner_ad_group, unchanged.auth_method) == ("Payroll", "g", "oauth")


async def test_patching_an_unknown_app_is_404(factory):
    with pytest.raises(HTTPException) as e:
        await patch_app("app_missing", PatchAppRequest(name="x"), _request(factory))
    assert e.value.status_code == 404
