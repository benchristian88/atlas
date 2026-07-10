import asyncio
import uuid

import httpx
import pytest

from atlas_plugin_sdk import ConnectionConfig, ConnectionValidator
from atlas_proxmox import ProxmoxConnectionValidator
from atlas_proxmox.client import api_token_header, validated_base_url

TOKEN_ID = "atlas@pve!discovery"
TOKEN_SECRET = "00000000-1111-2222-3333-444444444444"


def config(**overrides) -> ConnectionConfig:
    values = {
        "integration_id": uuid.uuid4(),
        "base_url": "https://pve.example.test:8006",
        "credentials": {"token_id": TOKEN_ID, "token_secret": TOKEN_SECRET},
        "verify_tls": True,
    }
    values.update(overrides)
    return ConnectionConfig(**values)


def validate(handler, connection_config=None):
    validator = ProxmoxConnectionValidator(transport=httpx.MockTransport(handler))
    return asyncio.run(validator.validate_connection(connection_config or config()))


def test_validator_implements_sdk_connection_contract() -> None:
    assert isinstance(ProxmoxConnectionValidator(), ConnectionValidator)


def test_success_uses_api_token_header_and_lists_nodes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://pve.example.test:8006/api2/json/nodes"
        assert request.headers["Authorization"] == (
            f"PVEAPIToken={TOKEN_ID}={TOKEN_SECRET}"
        )
        return httpx.Response(
            200,
            json={"data": [{"node": "pve-01"}, {"node": "pve-02"}]},
        )

    result = validate(handler)
    assert result.valid is True
    assert result.message == "Connection successful"
    assert result.details == {"node_count": 2}
    assert TOKEN_SECRET not in repr(result)


@pytest.mark.parametrize("status_code", [401, 403])
def test_rejected_or_underprivileged_token_is_sanitized(status_code: int) -> None:
    result = validate(lambda request: httpx.Response(status_code, json={"errors": TOKEN_SECRET}))
    assert result.valid is False
    assert result.details == {"status_code": status_code}
    assert TOKEN_SECRET not in result.message
    assert TOKEN_SECRET not in repr(result)


def test_timeout_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"secret={TOKEN_SECRET}", request=request)

    result = validate(handler)
    assert result == result.__class__(
        valid=False, message="Connection to Proxmox timed out"
    )


@pytest.mark.parametrize(
    ("response", "expected_message"),
    [
        (httpx.Response(200, text="not json"), "Proxmox returned an unexpected response"),
        (httpx.Response(200, json={"data": {}}), "Proxmox returned an unexpected response"),
        (httpx.Response(404), "Proxmox API nodes endpoint was not found"),
        (httpx.Response(500), "Proxmox API returned an unexpected HTTP status"),
    ],
)
def test_bad_responses_are_reported_without_response_content(
    response: httpx.Response, expected_message: str
) -> None:
    result = validate(lambda request: response)
    assert result.valid is False
    assert result.message == expected_message


@pytest.mark.parametrize(
    "base_url",
    [
        "http://pve.example.test:8006",
        "https://user:password@pve.example.test:8006",
        "https://pve.example.test:8006?token=secret",
        "https://pve.example.test:8006/proxy/path",
    ],
)
def test_unsafe_base_urls_are_rejected_before_request(base_url: str) -> None:
    result = validate(
        lambda request: pytest.fail("request should not be sent"),
        config(base_url=base_url),
    )
    assert result.valid is False


@pytest.mark.parametrize(
    "credentials",
    [
        {},
        {"token_id": TOKEN_ID},
        {"token_secret": TOKEN_SECRET},
        {"token_id": "invalid", "token_secret": TOKEN_SECRET},
    ],
)
def test_missing_or_invalid_credentials_are_rejected(credentials: dict[str, str]) -> None:
    result = validate(
        lambda request: pytest.fail("request should not be sent"),
        config(credentials=credentials),
    )
    assert result.valid is False
    assert TOKEN_SECRET not in result.message


def test_token_header_and_url_helpers() -> None:
    assert api_token_header(
        {"token_id": TOKEN_ID, "token_secret": TOKEN_SECRET}
    ) == f"PVEAPIToken={TOKEN_ID}={TOKEN_SECRET}"
    assert validated_base_url("https://pve.example.test:8006/") == (
        "https://pve.example.test:8006"
    )
