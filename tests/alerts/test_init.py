"""SC-ALT-18: Verify the public API of scanner.alerts.__init__."""
from __future__ import annotations


class TestSCALT18PublicAPI:
    def test_format_alert_importable(self) -> None:
        from scanner.alerts import format_alert
        assert callable(format_alert)

    def test_send_alert_importable(self) -> None:
        from scanner.alerts import send_alert
        assert callable(send_alert)

    def test_alert_delivery_error_importable(self) -> None:
        from scanner.alerts import AlertDeliveryError
        assert issubclass(AlertDeliveryError, Exception)

    def test_all_exports_present(self) -> None:
        import scanner.alerts as alerts_pkg
        assert hasattr(alerts_pkg, "__all__")
        assert set(alerts_pkg.__all__) == {"format_alert", "send_alert", "AlertDeliveryError"}
