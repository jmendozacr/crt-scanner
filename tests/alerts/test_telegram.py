"""Tests for scanner.alerts.telegram — SC-ALT-12 through SC-ALT-17."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from scanner.alerts.telegram import AlertDeliveryError, send_alert

# Patch target — we patch requests.post where it is USED
_POST = "scanner.alerts.telegram.requests.post"
_SETTINGS = "scanner.alerts.telegram.settings"


def _make_settings(token: str = "SECRET_TOKEN", chat_id: str = "123456") -> MagicMock:
    mock = MagicMock()
    mock.TELEGRAM_BOT_TOKEN = token
    mock.TELEGRAM_CHAT_ID = chat_id
    return mock


def _make_ok_response(ok: bool = True) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"ok": ok, "description": "some error" if not ok else None}
    return response


# ---------------------------------------------------------------------------
# SC-ALT-12: HTTP 200 + ok:true → returns None
# ---------------------------------------------------------------------------

class TestSCALT12SuccessReturnsNone:
    def test_returns_none_on_success(self) -> None:
        with patch(_POST, return_value=_make_ok_response(ok=True)), \
             patch(_SETTINGS, _make_settings()):
            result = send_alert("Hello")
            assert result is None


# ---------------------------------------------------------------------------
# SC-ALT-13: HTTP 200 + ok:false → AlertDeliveryError
# ---------------------------------------------------------------------------

class TestSCALT13OkFalseRaisesError:
    def test_raises_on_ok_false(self) -> None:
        with patch(_POST, return_value=_make_ok_response(ok=False)), \
             patch(_SETTINGS, _make_settings()):
            with pytest.raises(AlertDeliveryError) as exc_info:
                send_alert("Hello")
            assert "API error" in str(exc_info.value)

    def test_includes_description(self) -> None:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"ok": False, "description": "chat not found"}
        with patch(_POST, return_value=response), \
             patch(_SETTINGS, _make_settings()):
            with pytest.raises(AlertDeliveryError) as exc_info:
                send_alert("Hello")
            assert "chat not found" in str(exc_info.value)


# ---------------------------------------------------------------------------
# SC-ALT-14: HTTP non-2xx → AlertDeliveryError
# ---------------------------------------------------------------------------

class TestSCALT14NonSuccessHTTP:
    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 429, 500, 503])
    def test_raises_on_non_200(self, status_code: int) -> None:
        response = MagicMock()
        response.status_code = status_code
        with patch(_POST, return_value=response), \
             patch(_SETTINGS, _make_settings()):
            with pytest.raises(AlertDeliveryError) as exc_info:
                send_alert("Hello")
            assert f"HTTP {status_code}" in str(exc_info.value)


# ---------------------------------------------------------------------------
# SC-ALT-15: ConnectionError → AlertDeliveryError
# ---------------------------------------------------------------------------

class TestSCALT15ConnectionError:
    def test_raises_on_connection_error(self) -> None:
        with patch(_POST, side_effect=requests.exceptions.ConnectionError("refused")), \
             patch(_SETTINGS, _make_settings()):
            with pytest.raises(AlertDeliveryError) as exc_info:
                send_alert("Hello")
            assert "connection error" in str(exc_info.value)

    def test_reason_attribute_set(self) -> None:
        with patch(_POST, side_effect=requests.exceptions.ConnectionError()), \
             patch(_SETTINGS, _make_settings()):
            with pytest.raises(AlertDeliveryError) as exc_info:
                send_alert("Hello")
            assert exc_info.value.reason == "connection error"


# ---------------------------------------------------------------------------
# SC-ALT-16: Timeout → AlertDeliveryError
# ---------------------------------------------------------------------------

class TestSCALT16Timeout:
    def test_raises_on_timeout(self) -> None:
        with patch(_POST, side_effect=requests.exceptions.Timeout("timed out")), \
             patch(_SETTINGS, _make_settings()):
            with pytest.raises(AlertDeliveryError) as exc_info:
                send_alert("Hello")
            assert "timed out" in str(exc_info.value)

    def test_reason_attribute_set(self) -> None:
        with patch(_POST, side_effect=requests.exceptions.Timeout()), \
             patch(_SETTINGS, _make_settings()):
            with pytest.raises(AlertDeliveryError) as exc_info:
                send_alert("Hello")
            assert exc_info.value.reason == "request timed out"


# ---------------------------------------------------------------------------
# SC-ALT-17: token NEVER appears in error messages
# ---------------------------------------------------------------------------

class TestSCALT17TokenNeverInError:
    SECRET = "SUPER_SECRET_BOT_TOKEN_XYZ"

    def test_token_absent_from_connection_error(self) -> None:
        settings = _make_settings(token=self.SECRET)
        with patch(_POST, side_effect=requests.exceptions.ConnectionError()), \
             patch(_SETTINGS, settings):
            with pytest.raises(AlertDeliveryError) as exc_info:
                send_alert("Hello")
            assert self.SECRET not in str(exc_info.value)

    def test_token_absent_from_timeout_error(self) -> None:
        settings = _make_settings(token=self.SECRET)
        with patch(_POST, side_effect=requests.exceptions.Timeout()), \
             patch(_SETTINGS, settings):
            with pytest.raises(AlertDeliveryError) as exc_info:
                send_alert("Hello")
            assert self.SECRET not in str(exc_info.value)

    def test_token_absent_from_http_error(self) -> None:
        response = MagicMock()
        response.status_code = 403
        settings = _make_settings(token=self.SECRET)
        with patch(_POST, return_value=response), \
             patch(_SETTINGS, settings):
            with pytest.raises(AlertDeliveryError) as exc_info:
                send_alert("Hello")
            assert self.SECRET not in str(exc_info.value)

    def test_token_absent_from_api_error(self) -> None:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"ok": False, "description": "unauthorized"}
        settings = _make_settings(token=self.SECRET)
        with patch(_POST, return_value=response), \
             patch(_SETTINGS, settings):
            with pytest.raises(AlertDeliveryError) as exc_info:
                send_alert("Hello")
            assert self.SECRET not in str(exc_info.value)
