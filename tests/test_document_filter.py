"""src/common/document_filter.py 테스트."""

import re

from src.common.document_filter import EXCLUDE_PRESETS, apply_document_filters, resolve_exclude_pattern


class _Doc:
    def __init__(self, title, summary=None):
        self.title = title
        self.summary = summary if summary is not None else title


def test_resolve_returns_none_when_not_provided():
    assert resolve_exclude_pattern(None) is None
    assert resolve_exclude_pattern("") is None


def test_resolve_expands_structured_preset():
    pattern = resolve_exclude_pattern("structured")
    assert pattern == EXCLUDE_PRESETS["structured"]
    assert re.search(pattern, "제17-1회 파생결합증권(ELS) 발행결정")
    assert re.search(pattern, "주가연계증권(ELS) 발행실적보고서")
    assert not re.search(pattern, "주요사항보고서(회사합병결정)")


def test_resolve_passes_through_custom_regex():
    custom = "테스트패턴"
    assert resolve_exclude_pattern(custom) == custom


def test_apply_document_filters_excludes_by_title_pattern():
    docs = [_Doc("주가연계증권(ELS) 발행실적보고서"), _Doc("주요사항보고서(회사합병결정)")]
    result = apply_document_filters(docs, exclude_pattern="structured")
    assert [d.title for d in result] == ["주요사항보고서(회사합병결정)"]


def test_apply_document_filters_only_enriched_keeps_docs_with_different_summary():
    docs = [_Doc("제목만 있는 공시"), _Doc("원문이 채워진 공시", summary="실제 원문 내용...")]
    result = apply_document_filters(docs, only_enriched=True)
    assert [d.title for d in result] == ["원문이 채워진 공시"]


def test_apply_document_filters_returns_all_when_no_filters_given():
    docs = [_Doc("A"), _Doc("B")]
    assert apply_document_filters(docs) == docs
