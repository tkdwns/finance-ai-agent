"""NewsCollector 단위 테스트 (실제 네트워크 호출 없이 feedparser.parse를 모킹)."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from src.collectors.news_collector import NewsCollector


def _entry(title="제목", link="http://example.com/1", published=(2026, 7, 20, 9, 0, 0, 0, 0, 0), summary="요약"):
    return {
        "title": title,
        "link": link,
        "published_parsed": published,
        "summary": summary,
    }


def _mock_feed(entries, feed_title="테스트피드", bozo=False, bozo_exception=None):
    return SimpleNamespace(
        entries=entries,
        feed=SimpleNamespace(title=feed_title),
        bozo=bozo,
        bozo_exception=bozo_exception,
    )


def test_collect_returns_empty_when_no_rss_urls_configured():
    collector = NewsCollector(rss_urls=[])
    result = collector.collect(datetime(2026, 1, 1), datetime(2026, 12, 31))
    assert result == []


def test_collect_parses_entries_within_date_range():
    collector = NewsCollector(rss_urls=["http://feed.example.com/rss"])
    with patch("src.collectors.news_collector.feedparser.parse") as mock_parse:
        mock_parse.return_value = _mock_feed([_entry()])
        result = collector.collect(datetime(2026, 7, 1), datetime(2026, 7, 31))

    assert len(result) == 1
    item = result[0]
    assert item.title == "제목"
    assert item.url == "http://example.com/1"
    assert item.published_at == datetime(2026, 7, 20, 9, 0, 0)
    assert item.source == "테스트피드"
    assert item.summary == "요약"


def test_collect_leaves_asset_class_empty_for_tagger_to_fill():
    """자산군 분류는 news_collector가 아니라 preprocessing.tagger가 담당해야 한다."""
    collector = NewsCollector(rss_urls=["http://feed.example.com/rss"])
    with patch("src.collectors.news_collector.feedparser.parse") as mock_parse:
        mock_parse.return_value = _mock_feed([_entry()])
        result = collector.collect(datetime(2026, 7, 1), datetime(2026, 7, 31))

    assert result[0].asset_class == ""


def test_collect_filters_out_entries_outside_date_range():
    collector = NewsCollector(rss_urls=["http://feed.example.com/rss"])
    in_range = _entry(link="http://example.com/in", published=(2026, 7, 20, 9, 0, 0, 0, 0, 0))
    out_of_range = _entry(link="http://example.com/out", published=(2026, 1, 1, 9, 0, 0, 0, 0, 0))
    with patch("src.collectors.news_collector.feedparser.parse") as mock_parse:
        mock_parse.return_value = _mock_feed([in_range, out_of_range])
        result = collector.collect(datetime(2026, 7, 1), datetime(2026, 7, 31))

    assert len(result) == 1
    assert result[0].url == "http://example.com/in"


def test_collect_skips_entries_missing_title_or_link():
    collector = NewsCollector(rss_urls=["http://feed.example.com/rss"])
    missing_title = _entry(title="", link="http://example.com/2")
    missing_link = _entry(title="제목만 있음", link="")
    with patch("src.collectors.news_collector.feedparser.parse") as mock_parse:
        mock_parse.return_value = _mock_feed([missing_title, missing_link])
        result = collector.collect(datetime(2026, 7, 1), datetime(2026, 7, 31))

    assert result == []


def test_collect_skips_entries_without_published_date():
    collector = NewsCollector(rss_urls=["http://feed.example.com/rss"])
    no_date_entry = {"title": "제목", "link": "http://example.com/3", "summary": "요약"}
    with patch("src.collectors.news_collector.feedparser.parse") as mock_parse:
        mock_parse.return_value = _mock_feed([no_date_entry])
        result = collector.collect(datetime(2026, 7, 1), datetime(2026, 7, 31))

    assert result == []


def test_collect_continues_when_one_feed_fails():
    """피드 하나가 파싱 실패(bozo)해도 나머지 피드는 계속 수집되어야 한다."""
    collector = NewsCollector(rss_urls=["http://broken.example.com/rss", "http://ok.example.com/rss"])
    broken = _mock_feed([], bozo=True, bozo_exception=Exception("연결 실패"))
    ok = _mock_feed([_entry(link="http://example.com/ok")])

    with patch("src.collectors.news_collector.feedparser.parse", side_effect=[broken, ok]):
        result = collector.collect(datetime(2026, 7, 1), datetime(2026, 7, 31))

    assert len(result) == 1
    assert result[0].url == "http://example.com/ok"


def test_collect_merges_results_from_multiple_feeds():
    collector = NewsCollector(rss_urls=["http://a.example.com/rss", "http://b.example.com/rss"])
    feed_a = _mock_feed([_entry(link="http://example.com/a")], feed_title="A언론사")
    feed_b = _mock_feed([_entry(link="http://example.com/b")], feed_title="B언론사")

    with patch("src.collectors.news_collector.feedparser.parse", side_effect=[feed_a, feed_b]):
        result = collector.collect(datetime(2026, 7, 1), datetime(2026, 7, 31))

    assert {r.url for r in result} == {"http://example.com/a", "http://example.com/b"}
    assert {r.source for r in result} == {"A언론사", "B언론사"}


def test_collector_uses_explicit_rss_urls_over_settings_default(monkeypatch):
    monkeypatch.setattr("src.collectors.news_collector.settings.news_rss_urls", ["http://settings-default.example.com"])
    collector = NewsCollector(rss_urls=["http://explicit.example.com"])
    assert collector.rss_urls == ["http://explicit.example.com"]


def test_collector_falls_back_to_settings_when_no_rss_urls_given(monkeypatch):
    monkeypatch.setattr("src.collectors.news_collector.settings.news_rss_urls", ["http://settings-default.example.com"])
    collector = NewsCollector()
    assert collector.rss_urls == ["http://settings-default.example.com"]
