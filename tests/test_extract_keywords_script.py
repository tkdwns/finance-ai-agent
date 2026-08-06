"""scripts/extract_keywords.py의 헬퍼 함수 테스트."""

from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts.extract_keywords import _extract_and_save_for_class
from src.storage.models import Base, Keyword, PeriodType
from src.storage.queries import UnifiedDocument


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _doc(asset_class="bond", title="제목", summary="요약", url="http://a.com/1"):
    return UnifiedDocument(
        asset_class=asset_class,
        content_type="news",
        source="테스트",
        title=title,
        url=url,
        summary=summary,
        published_at=datetime(2026, 7, 20),
    )


def test_extract_and_save_stores_keywords_with_given_asset_class(session):
    docs = [_doc(asset_class="bond", title="A", summary="채권 시장 요약")]
    with patch(
        "scripts.extract_keywords.extract_keywords",
        return_value=[{"keyword": "금리", "score": 1.0, "explanation": "설명"}],
    ):
        saved, results = _extract_and_save_for_class(
            session, docs, "bond", PeriodType.WEEKLY,
            datetime(2026, 7, 20), datetime(2026, 7, 27),
            top_n=10, use_llm=True, only_enriched=False, max_df=0.5, provider=None,
        )

    assert saved == 1
    assert results[0]["keyword"] == "금리"
    row = session.execute(select(Keyword)).scalar_one()
    assert row.asset_class == "bond"
    assert row.keyword == "금리"


def test_extract_and_save_updates_existing_keyword(session):
    docs = [_doc()]
    with patch(
        "scripts.extract_keywords.extract_keywords",
        return_value=[{"keyword": "금리", "score": 1.0, "explanation": "첫 설명"}],
    ):
        _extract_and_save_for_class(
            session, docs, "bond", PeriodType.WEEKLY,
            datetime(2026, 7, 20), datetime(2026, 7, 27),
            top_n=10, use_llm=True, only_enriched=False, max_df=0.5, provider=None,
        )

    with patch(
        "scripts.extract_keywords.extract_keywords",
        return_value=[{"keyword": "금리", "score": 2.0, "explanation": "갱신된 설명"}],
    ):
        saved, _ = _extract_and_save_for_class(
            session, docs, "bond", PeriodType.WEEKLY,
            datetime(2026, 7, 20), datetime(2026, 7, 27),
            top_n=10, use_llm=True, only_enriched=False, max_df=0.5, provider=None,
        )

    assert saved == 0  # 새로 저장된 건 없음(기존 갱신)
    row = session.execute(select(Keyword)).scalar_one()
    assert row.score == 2.0
    assert row.explanation == "갱신된 설명"


def test_extract_and_save_only_enriched_filters_title_only_documents(session):
    """summary가 title과 동일한(원문 없이 제목만 있는) 문서는 --only-enriched 시 제외되어야 한다."""
    title_only = _doc(title="제목뿐인 공시", summary="제목뿐인 공시", url="http://a.com/2")
    enriched = _doc(title="공시 제목", summary="실제 원문 내용이 담긴 요약", url="http://a.com/3")

    with patch("scripts.extract_keywords.extract_keywords", return_value=[]) as mock_extract:
        _extract_and_save_for_class(
            session, [title_only, enriched], "bond", PeriodType.WEEKLY,
            datetime(2026, 7, 20), datetime(2026, 7, 27),
            top_n=10, use_llm=True, only_enriched=True, max_df=0.5, provider=None,
        )

    called_texts = mock_extract.call_args.args[0]
    assert called_texts == ["실제 원문 내용이 담긴 요약"]


def test_extract_and_save_returns_zero_when_no_keywords_extracted(session):
    with patch("scripts.extract_keywords.extract_keywords", return_value=[]):
        saved, results = _extract_and_save_for_class(
            session, [_doc()], "bond", PeriodType.WEEKLY,
            datetime(2026, 7, 20), datetime(2026, 7, 27),
            top_n=10, use_llm=True, only_enriched=False, max_df=0.5, provider=None,
        )

    assert (saved, results) == (0, [])
