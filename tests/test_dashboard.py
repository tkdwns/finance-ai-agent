"""src/web/dashboard.py 테스트 (Flask test client + 인메모리 SQLite)."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.web.dashboard as dashboard_module
from src.storage.models import AssetClass, Base, PeriodType, Report


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def client(session_factory, monkeypatch):
    monkeypatch.setattr(dashboard_module, "get_session", session_factory)
    app = dashboard_module.create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _add_report(session_factory, **overrides):
    defaults = dict(
        period_type=PeriodType.WEEKLY,
        period_start=datetime(2026, 7, 1),
        period_end=datetime(2026, 7, 7),
        asset_class=None,
        content_markdown="# 주간 리포트\n\n본문 내용입니다.",
        generated_at=datetime(2026, 7, 8, 9, 0),
    )
    defaults.update(overrides)
    session = session_factory()
    session.add(Report(**defaults))
    session.commit()
    session.close()


def test_index_shows_empty_message_when_no_reports(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "생성된 리포트가 없습니다" in resp.get_data(as_text=True)


def test_index_lists_saved_reports(session_factory, client):
    _add_report(session_factory)
    resp = client.get("/")
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "주간" in text
    assert "2026-07-01" in text
    assert "/report/1" in text


def test_index_shows_asset_class_when_set(session_factory, client):
    _add_report(session_factory, asset_class=AssetClass.STOCK)
    text = client.get("/").get_data(as_text=True)
    assert "stock" in text


def test_view_report_renders_markdown_content(session_factory, client):
    _add_report(session_factory, content_markdown="# 제목\n\n**굵게** 표시된 본문")
    resp = client.get("/report/1")
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "<h1>제목</h1>" in text
    assert "<strong>굵게</strong>" in text


def test_view_report_rewrites_relative_chart_src_to_absolute(session_factory, client):
    _add_report(session_factory, content_markdown='<img src="charts/x.png">')
    text = client.get("/report/1").get_data(as_text=True)
    assert 'src="/charts/x.png"' in text


def test_view_report_returns_404_for_unknown_id(client):
    resp = client.get("/report/999")
    assert resp.status_code == 404


def test_chart_image_serves_file_from_reports_output_charts(monkeypatch, client, tmp_path):
    chart_dir = tmp_path / "charts"
    chart_dir.mkdir()
    (chart_dir / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(dashboard_module.settings, "reports_output_dir", tmp_path)

    resp = client.get("/charts/a.png")
    assert resp.status_code == 200
    assert resp.data == b"\x89PNG\r\n\x1a\n"


def test_chart_image_returns_404_for_missing_file(monkeypatch, client, tmp_path):
    (tmp_path / "charts").mkdir()
    monkeypatch.setattr(dashboard_module.settings, "reports_output_dir", tmp_path)

    resp = client.get("/charts/missing.png")
    assert resp.status_code == 404
