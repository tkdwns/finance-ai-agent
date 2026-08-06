"""전처리 모듈(정규화/중복제거/자산군 태깅) 단위 테스트."""

from datetime import datetime, timedelta

from src.collectors.base import RawItem
from src.preprocessing.deduplicator import deduplicate
from src.preprocessing.normalizer import normalize_text
from src.preprocessing.pipeline import preprocess
from src.preprocessing.tagger import guess_asset_class, tag_asset_class


def _make_item(title, url, published_at, asset_class="", summary=""):
    return RawItem(
        source="test",
        asset_class=asset_class,
        title=title,
        url=url,
        published_at=published_at,
        summary=summary,
    )


def test_normalize_text_strips_html_and_whitespace():
    raw = "<p>코스피   지수가  \n\n 상승했다.</p>"
    assert normalize_text(raw) == "코스피 지수가 상승했다."


def test_normalize_text_handles_empty_string():
    assert normalize_text("") == ""


def test_guess_asset_class_matches_keywords():
    assert guess_asset_class("코스피 지수가 급등했다") == "stock"
    assert guess_asset_class("국고채 금리가 하락했다") == "bond"
    assert guess_asset_class("아파트 실거래가 신고가") == "real_estate"
    assert guess_asset_class("비트코인 가격이 급등했다") == "crypto"


def test_guess_asset_class_returns_none_when_no_match():
    assert guess_asset_class("오늘 날씨가 맑습니다") is None


def test_tag_asset_class_preserves_existing_value():
    item = _make_item("아무 제목", "http://x.com/1", datetime.now(), asset_class="stock")
    tagged = tag_asset_class(item)
    assert tagged.asset_class == "stock"


def test_tag_asset_class_fills_unknown_when_no_match():
    item = _make_item("오늘 날씨가 맑습니다", "http://x.com/2", datetime.now())
    tagged = tag_asset_class(item)
    assert tagged.asset_class == "unknown"


def test_deduplicate_removes_exact_url_duplicates():
    now = datetime.now()
    items = [
        _make_item("제목A", "http://x.com/1", now),
        _make_item("제목A", "http://x.com/1", now),
    ]
    result = deduplicate(items)
    assert len(result) == 1


def test_deduplicate_removes_similar_titles_and_keeps_earliest():
    now = datetime.now()
    earlier = now - timedelta(hours=2)
    items = [
        _make_item("코스피 2900 돌파, 사상 최고치 경신", "http://a.com/1", now),
        _make_item("코스피 2900 돌파,사상 최고치 경신!", "http://b.com/2", earlier),
    ]
    result = deduplicate(items, title_similarity_threshold=0.85)
    assert len(result) == 1
    assert result[0].url == "http://b.com/2"  # 더 이른 기사가 남아야 함


def test_deduplicate_keeps_distinct_titles():
    now = datetime.now()
    items = [
        _make_item("코스피 상승 마감", "http://a.com/1", now),
        _make_item("국고채 금리 하락", "http://b.com/2", now),
    ]
    result = deduplicate(items)
    assert len(result) == 2


def test_deduplicate_with_none_threshold_keeps_same_titles_from_different_sources():
    """DART 공시처럼 다른 회사의 공시가 제목이 겹치는 경우, title dedup을 꺼야
    서로 다른 회사의 공시가 잘못 병합되지 않는다."""
    now = datetime.now()
    items = [
        _make_item("분기보고서 (2025.12)", "http://dart.com/rcept1", now),
        _make_item("분기보고서 (2025.12)", "http://dart.com/rcept2", now),
    ]
    result = deduplicate(items, title_similarity_threshold=None)
    assert len(result) == 2


def test_preprocess_pipeline_end_to_end():
    now = datetime.now()
    items = [
        _make_item(
            "<b>비트코인</b> 급등",
            "http://a.com/1",
            now,
            summary="  가상자산 시장이   출렁였다  ",
        ),
    ]
    result = preprocess(items)
    assert len(result) == 1
    assert result[0].title == "비트코인 급등"
    assert result[0].summary == "가상자산 시장이 출렁였다"
    assert result[0].asset_class == "crypto"
