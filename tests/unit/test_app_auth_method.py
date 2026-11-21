"""The auth method an app is created with: how it signs its own users in."""
import pytest
from pydantic import ValidationError

from api.models import APP_AUTH_METHODS, CreateAppRequest, PatchAppRequest
from core.enums import AuthMethod


def _app(**fields) -> CreateAppRequest:
    return CreateAppRequest(**{"name": "Payroll", "url": "https://payroll.corp.internal", "owner_ad_group": "g", **fields})


def test_the_methods_an_app_may_declare():
    assert APP_AUTH_METHODS == {
        AuthMethod.oauth,
        AuthMethod.login_redirect,
        AuthMethod.unauthenticated,
        AuthMethod.kerberos,
    }


@pytest.mark.parametrize("method", sorted(m.value for m in APP_AUTH_METHODS))
def test_an_app_keeps_its_declared_method(method):
    assert _app(auth_method=method).auth_method is AuthMethod(method)


@pytest.mark.parametrize("method", [
    # Blockers: such an app cannot be published at all.
    "ntlm", "basic", "other",
    # Only the scanners say they could not tell.
    "unknown", "no_response", "dns_failed",
    # Whoever registers the app knows the mechanism.
    "negotiate",
    # How APIs are called, not how a person signs in.
    "bearer", "api_key",
])
def test_an_app_method_is_refused(method):
    with pytest.raises(ValidationError, match="an app's auth method must be one of"):
        _app(auth_method=method)


def test_a_value_outside_the_vocabulary_is_refused():
    with pytest.raises(ValidationError):
        _app(auth_method="saml")


def test_an_app_must_declare_its_method():
    with pytest.raises(ValidationError):
        _app()


def test_a_patch_checks_the_method_as_creating_does():
    assert PatchAppRequest(auth_method="kerberos").auth_method is AuthMethod.kerberos
    with pytest.raises(ValidationError, match="an app's auth method must be one of"):
        PatchAppRequest(auth_method="ntlm")


def test_a_patch_may_name_no_field():
    assert PatchAppRequest().model_dump() == {"name": None, "owner_ad_group": None, "auth_method": None}


@pytest.mark.parametrize("field", ["url", "id", "current_scan_id"])
def test_a_patch_refuses_a_field_it_cannot_change(field):
    # Refused rather than ignored, so a client never reads success for a URL change.
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PatchAppRequest(**{field: "x"})
