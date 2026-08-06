"""src/reports/emailer.py 테스트 (실제 SMTP 연결 없이 smtplib.SMTP를 모킹)."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from src.reports import emailer

# 최소 크기의 유효한 1x1 투명 PNG (MIMEImage가 서브타입을 인식할 수 있어야 하므로
# 임의 바이트 대신 실제 PNG 시그니처를 쓴다).
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@pytest.fixture(autouse=True)
def _configure_smtp(monkeypatch):
    monkeypatch.setattr(emailer.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(emailer.settings, "smtp_port", 587)
    monkeypatch.setattr(emailer.settings, "smtp_user", "bot@example.com")
    monkeypatch.setattr(emailer.settings, "smtp_password", "pw")
    monkeypatch.setattr(emailer.settings, "report_email_from", "")


def test_markdown_to_html_renders_basic_content():
    html = emailer._markdown_to_html("# 제목\n\n본문 내용")
    assert "<h1>제목</h1>" in html
    assert "본문 내용" in html


def test_markdown_to_html_passes_through_raw_html_table():
    # report_template.md.j2가 만드는 <table>/<img>는 markdown 라이브러리가 그대로 통과시켜야 한다.
    md = '<table><tr><td><img src="charts/x.png"></td></tr></table>'
    html = emailer._markdown_to_html(md)
    assert '<img src="charts/x.png">' in html


def test_embed_images_replaces_src_with_cid_and_returns_attachment(tmp_path):
    chart_dir = tmp_path / "reports_output" / "charts"
    chart_dir.mkdir(parents=True)
    (chart_dir / "a.png").write_bytes(_PNG_1X1)

    html = '<img src="charts/a.png">'
    new_html, images = emailer._embed_images(html, str(chart_dir))

    assert 'src="cid:a.png"' in new_html
    assert len(images) == 1
    assert images[0]["Content-ID"] == "<a.png>"


def test_embed_images_leaves_src_unchanged_when_file_missing(tmp_path):
    chart_dir = tmp_path / "reports_output" / "charts"
    chart_dir.mkdir(parents=True)

    html = '<img src="charts/missing.png">'
    new_html, images = emailer._embed_images(html, str(chart_dir))

    assert new_html == html
    assert images == []


def test_send_report_email_raises_when_smtp_host_missing(monkeypatch):
    monkeypatch.setattr(emailer.settings, "smtp_host", "")
    with pytest.raises(RuntimeError):
        emailer.send_report_email("제목", "본문", ["a@example.com"])


def test_send_report_email_raises_when_no_recipients():
    with pytest.raises(RuntimeError):
        emailer.send_report_email("제목", "본문", [])


def test_send_report_email_sends_via_smtp():
    with patch("src.reports.emailer.smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_server

        emailer.send_report_email("제목", "# 리포트\n본문", ["a@example.com", "b@example.com"])

    mock_smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=15)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("bot@example.com", "pw")
    assert mock_server.sendmail.call_count == 1
    from_addr, to_addrs, _raw_message = mock_server.sendmail.call_args.args
    assert from_addr == "bot@example.com"
    assert to_addrs == ["a@example.com", "b@example.com"]


def test_send_report_email_uses_report_email_from_when_set(monkeypatch):
    monkeypatch.setattr(emailer.settings, "report_email_from", "reports@example.com")
    with patch("src.reports.emailer.smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_server

        emailer.send_report_email("제목", "본문", ["a@example.com"])

    from_addr = mock_server.sendmail.call_args.args[0]
    assert from_addr == "reports@example.com"


def test_send_report_email_embeds_chart_images(tmp_path):
    import email

    chart_dir = tmp_path / "reports_output" / "charts"
    chart_dir.mkdir(parents=True)
    (chart_dir / "chart1.png").write_bytes(_PNG_1X1)

    with patch("src.reports.emailer.smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_server

        emailer.send_report_email(
            "제목",
            '<img src="charts/chart1.png">',
            ["a@example.com"],
            chart_dir=str(chart_dir),
        )

    raw_message = mock_server.sendmail.call_args.args[2]
    parsed = email.message_from_string(raw_message)
    parts = list(parsed.walk())

    html_part = next(p for p in parts if p.get_content_type() == "text/html")
    assert "cid:chart1.png" in html_part.get_payload(decode=True).decode("utf-8")

    image_part = next(p for p in parts if p.get_content_type() == "image/png")
    assert image_part["Content-ID"] == "<chart1.png>"
