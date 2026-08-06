"""scripts/send_report_email.py의 핵심 로직(run_send_report_email) 테스트."""

from unittest.mock import patch

import pytest

import scripts.send_report_email as script_module


def _stub_report():
    return {"output_path": "reports_output/x.md", "content": "# 리포트\n본문"}


def test_run_send_report_email_uses_explicit_to_addrs():
    with patch.object(script_module, "run_generate_report", return_value=_stub_report()) as mock_gen, \
         patch.object(script_module, "send_report_email") as mock_send:
        result = script_module.run_send_report_email(days=7, period_type="weekly", to_addrs=["a@example.com"])

    mock_gen.assert_called_once()
    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["to_addrs"] == ["a@example.com"]
    assert mock_send.call_args.kwargs["markdown_content"] == "# 리포트\n본문"
    assert result["sent_to"] == ["a@example.com"]


def test_run_send_report_email_falls_back_to_settings_recipients(monkeypatch):
    monkeypatch.setattr(script_module.settings, "report_email_to", ["b@example.com"])
    with patch.object(script_module, "run_generate_report", return_value=_stub_report()), \
         patch.object(script_module, "send_report_email") as mock_send:
        script_module.run_send_report_email(days=7, period_type="weekly")

    assert mock_send.call_args.kwargs["to_addrs"] == ["b@example.com"]


def test_run_send_report_email_raises_when_no_recipients_anywhere(monkeypatch):
    monkeypatch.setattr(script_module.settings, "report_email_to", [])
    with patch.object(script_module, "run_generate_report", return_value=_stub_report()):
        with pytest.raises(RuntimeError):
            script_module.run_send_report_email(days=7, period_type="weekly")


def test_run_send_report_email_subject_includes_period_label():
    with patch.object(script_module, "run_generate_report", return_value=_stub_report()), \
         patch.object(script_module, "send_report_email") as mock_send:
        script_module.run_send_report_email(days=30, period_type="monthly", to_addrs=["a@example.com"])

    assert "월간" in mock_send.call_args.kwargs["subject"]
