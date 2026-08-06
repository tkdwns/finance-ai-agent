"""src/scheduler/jobs.py의 파이프라인 조합 로직 테스트 (내부 run_* 함수는 모킹)."""

from unittest.mock import patch

import src.scheduler.jobs as jobs_module


def _patch_pipeline_steps(report_result=None):
    """파이프라인의 수집/키워드/보고서 단계를 전부 스텁으로 교체하는 patch 목록을 만든다."""
    report_result = report_result if report_result is not None else {"output_path": "x.md", "content": "# 리포트"}
    return [
        patch.object(jobs_module, "run_collect_dart", return_value={}),
        patch.object(jobs_module, "run_collect_bond", return_value={}),
        patch.object(jobs_module, "run_collect_fred", return_value={}),
        patch.object(jobs_module, "run_collect_news", return_value={}),
        patch.object(jobs_module, "run_collect_real_estate", return_value={}),
        patch.object(jobs_module, "run_collect_law", return_value={}),
        patch.object(jobs_module, "run_extract_keywords", return_value={}),
        patch.object(jobs_module, "run_generate_report", return_value=report_result),
    ]


def test_run_daily_pipeline_calls_steps_in_order_with_expected_args():
    with patch.object(jobs_module, "run_collect_dart", return_value={"saved": 1}) as mock_collect, \
         patch.object(jobs_module, "run_collect_bond", return_value={"saved": 9}) as mock_bond, \
         patch.object(jobs_module, "run_collect_fred", return_value={"saved": 2}) as mock_fred, \
         patch.object(jobs_module, "run_collect_news", return_value={"saved": 3}) as mock_news, \
         patch.object(jobs_module, "run_collect_real_estate", return_value={"saved": 4}) as mock_real_estate, \
         patch.object(jobs_module, "run_collect_law", return_value={"saved": 1}) as mock_law, \
         patch.object(jobs_module, "run_extract_keywords", return_value={"saved": 2}) as mock_keywords, \
         patch.object(jobs_module, "run_generate_report", return_value={"output_path": "x.md"}) as mock_report:

        result = jobs_module.run_daily_pipeline()

    mock_collect.assert_called_once()
    assert mock_collect.call_args.kwargs["days"] == 1
    assert mock_collect.call_args.kwargs["fetch_text"] is True

    mock_bond.assert_called_once()
    assert mock_bond.call_args.kwargs["days"] == 1

    mock_fred.assert_called_once()
    assert mock_fred.call_args.kwargs["days"] == 1

    mock_news.assert_called_once()
    assert mock_news.call_args.kwargs["days"] == 1

    mock_real_estate.assert_called_once()
    assert mock_real_estate.call_args.kwargs["days"] == 1

    mock_law.assert_called_once()
    assert mock_law.call_args.kwargs["days"] == 1

    mock_keywords.assert_called_once()
    assert mock_keywords.call_args.kwargs["days"] == 1
    assert mock_keywords.call_args.kwargs["only_enriched"] is True
    assert mock_keywords.call_args.kwargs["exclude_pattern"] == "structured"

    mock_report.assert_called_once()
    assert mock_report.call_args.kwargs["days"] == 1
    assert mock_report.call_args.kwargs["period_type"] == "daily"

    assert result == {
        "collect": {"saved": 1},
        "bond": {"saved": 9},
        "fred": {"saved": 2},
        "news": {"saved": 3},
        "real_estate": {"saved": 4},
        "law": {"saved": 1},
        "keywords": {"saved": 2},
        "report": {"output_path": "x.md"},
    }


def test_run_weekly_pipeline_uses_seven_days():
    with patch.object(jobs_module, "run_collect_dart", return_value={}) as mock_collect, \
         patch.object(jobs_module, "run_collect_bond", return_value={}) as mock_bond, \
         patch.object(jobs_module, "run_collect_fred", return_value={}) as mock_fred, \
         patch.object(jobs_module, "run_collect_news", return_value={}) as mock_news, \
         patch.object(jobs_module, "run_collect_real_estate", return_value={}) as mock_real_estate, \
         patch.object(jobs_module, "run_collect_law", return_value={}) as mock_law, \
         patch.object(jobs_module, "run_extract_keywords", return_value={}), \
         patch.object(jobs_module, "run_generate_report", return_value={}) as mock_report:

        jobs_module.run_weekly_pipeline()

    assert mock_collect.call_args.kwargs["days"] == 7
    assert mock_bond.call_args.kwargs["days"] == 7
    assert mock_fred.call_args.kwargs["days"] == 7
    assert mock_news.call_args.kwargs["days"] == 7
    assert mock_real_estate.call_args.kwargs["days"] == 7
    assert mock_law.call_args.kwargs["days"] == 7
    assert mock_report.call_args.kwargs["period_type"] == "weekly"


def test_run_monthly_pipeline_uses_thirty_days():
    with patch.object(jobs_module, "run_collect_dart", return_value={}) as mock_collect, \
         patch.object(jobs_module, "run_collect_bond", return_value={}) as mock_bond, \
         patch.object(jobs_module, "run_collect_fred", return_value={}) as mock_fred, \
         patch.object(jobs_module, "run_collect_news", return_value={}) as mock_news, \
         patch.object(jobs_module, "run_collect_real_estate", return_value={}) as mock_real_estate, \
         patch.object(jobs_module, "run_collect_law", return_value={}) as mock_law, \
         patch.object(jobs_module, "run_extract_keywords", return_value={}), \
         patch.object(jobs_module, "run_generate_report", return_value={}) as mock_report:

        jobs_module.run_monthly_pipeline()

    assert mock_collect.call_args.kwargs["days"] == 30
    assert mock_bond.call_args.kwargs["days"] == 30
    assert mock_fred.call_args.kwargs["days"] == 30
    assert mock_news.call_args.kwargs["days"] == 30
    assert mock_real_estate.call_args.kwargs["days"] == 30
    assert mock_law.call_args.kwargs["days"] == 30
    assert mock_report.call_args.kwargs["period_type"] == "monthly"


def test_run_yearly_pipeline_uses_365_days():
    with patch.object(jobs_module, "run_collect_dart", return_value={}) as mock_collect, \
         patch.object(jobs_module, "run_collect_bond", return_value={}) as mock_bond, \
         patch.object(jobs_module, "run_collect_fred", return_value={}) as mock_fred, \
         patch.object(jobs_module, "run_collect_news", return_value={}) as mock_news, \
         patch.object(jobs_module, "run_collect_real_estate", return_value={}) as mock_real_estate, \
         patch.object(jobs_module, "run_collect_law", return_value={}) as mock_law, \
         patch.object(jobs_module, "run_extract_keywords", return_value={}), \
         patch.object(jobs_module, "run_generate_report", return_value={}) as mock_report:

        jobs_module.run_yearly_pipeline()

    assert mock_collect.call_args.kwargs["days"] == 365
    assert mock_bond.call_args.kwargs["days"] == 365
    assert mock_fred.call_args.kwargs["days"] == 365
    assert mock_news.call_args.kwargs["days"] == 365
    assert mock_real_estate.call_args.kwargs["days"] == 365
    assert mock_law.call_args.kwargs["days"] == 365
    assert mock_report.call_args.kwargs["period_type"] == "yearly"


def test_all_pipelines_use_recommended_substantial_pblntf_types():
    """모든 파이프라인이 절차성 신고(D 지분공시 등)를 제외한 추천 유형 조합을 써야 한다."""
    with patch.object(jobs_module, "run_collect_dart", return_value={}) as mock_collect, \
         patch.object(jobs_module, "run_collect_bond", return_value={}), \
         patch.object(jobs_module, "run_collect_fred", return_value={}), \
         patch.object(jobs_module, "run_collect_news", return_value={}), \
         patch.object(jobs_module, "run_collect_real_estate", return_value={}), \
         patch.object(jobs_module, "run_collect_law", return_value={}), \
         patch.object(jobs_module, "run_extract_keywords", return_value={}), \
         patch.object(jobs_module, "run_generate_report", return_value={}):

        jobs_module.run_daily_pipeline()

    assert mock_collect.call_args.kwargs["pblntf_types"] == ["A", "B", "C"]


def test_daily_pipeline_still_runs_report_even_if_bond_collection_fails():
    """ECOS 키 미설정 등으로 run_collect_bond가 에러 dict를 반환해도(예외를 던지지 않음)
    나머지 파이프라인(키워드 추출/보고서 생성)은 계속 진행되어야 한다."""
    with patch.object(jobs_module, "run_collect_dart", return_value={}), \
         patch.object(jobs_module, "run_collect_bond", return_value={"collected": 0, "saved": 0, "updated": 0, "error": "ECOS_API_KEY가 설정되지 않았습니다."}), \
         patch.object(jobs_module, "run_collect_fred", return_value={}), \
         patch.object(jobs_module, "run_collect_news", return_value={}), \
         patch.object(jobs_module, "run_collect_real_estate", return_value={}), \
         patch.object(jobs_module, "run_collect_law", return_value={}), \
         patch.object(jobs_module, "run_extract_keywords", return_value={}), \
         patch.object(jobs_module, "run_generate_report", return_value={"output_path": "x.md"}) as mock_report:

        result = jobs_module.run_daily_pipeline()

    mock_report.assert_called_once()
    assert "error" in result["bond"]


def test_daily_pipeline_still_runs_report_even_if_fred_collection_fails():
    """FRED_API_KEY 미설정 등으로 run_collect_fred가 에러 dict를 반환해도(예외를 던지지 않음)
    나머지 파이프라인은 그대로 진행되어야 한다."""
    error_result = {"collected": 0, "saved": 0, "updated": 0, "error": "FRED_API_KEY가 설정되지 않았습니다."}
    with patch.object(jobs_module, "run_collect_dart", return_value={}), \
         patch.object(jobs_module, "run_collect_bond", return_value={}), \
         patch.object(jobs_module, "run_collect_fred", return_value=error_result) as mock_fred, \
         patch.object(jobs_module, "run_collect_news", return_value={}), \
         patch.object(jobs_module, "run_collect_real_estate", return_value={}), \
         patch.object(jobs_module, "run_collect_law", return_value={}), \
         patch.object(jobs_module, "run_extract_keywords", return_value={}), \
         patch.object(jobs_module, "run_generate_report", return_value={"output_path": "x.md"}) as mock_report:

        result = jobs_module.run_daily_pipeline()

    mock_fred.assert_called_once()
    mock_report.assert_called_once()
    assert "error" in result["fred"]


def test_daily_pipeline_still_runs_report_even_if_news_rss_not_configured():
    """NEWS_RSS_URLS가 비어 있어 run_collect_news가 0건 결과를 반환해도
    나머지 파이프라인은 그대로 진행되어야 한다."""
    empty_news_result = {"collected": 0, "stock": 0, "bond": 0, "skipped_duplicate": 0, "skipped_unmapped": 0}
    with patch.object(jobs_module, "run_collect_dart", return_value={}), \
         patch.object(jobs_module, "run_collect_bond", return_value={}), \
         patch.object(jobs_module, "run_collect_fred", return_value={}), \
         patch.object(jobs_module, "run_collect_news", return_value=empty_news_result) as mock_news, \
         patch.object(jobs_module, "run_collect_real_estate", return_value={}), \
         patch.object(jobs_module, "run_collect_law", return_value={}), \
         patch.object(jobs_module, "run_extract_keywords", return_value={}), \
         patch.object(jobs_module, "run_generate_report", return_value={"output_path": "x.md"}) as mock_report:

        result = jobs_module.run_daily_pipeline()

    mock_news.assert_called_once()
    mock_report.assert_called_once()
    assert result["news"] == empty_news_result


def test_daily_pipeline_still_runs_report_even_if_real_estate_collection_fails():
    """MOLIT_API_KEY 미설정 등으로 run_collect_real_estate가 에러 dict를 반환해도
    (예외를 던지지 않음) 나머지 파이프라인은 그대로 진행되어야 한다."""
    error_result = {"collected": 0, "saved": 0, "skipped": 0, "error": "MOLIT_API_KEY가 설정되지 않았습니다."}
    with patch.object(jobs_module, "run_collect_dart", return_value={}), \
         patch.object(jobs_module, "run_collect_bond", return_value={}), \
         patch.object(jobs_module, "run_collect_fred", return_value={}), \
         patch.object(jobs_module, "run_collect_news", return_value={}), \
         patch.object(jobs_module, "run_collect_real_estate", return_value=error_result) as mock_real_estate, \
         patch.object(jobs_module, "run_collect_law", return_value={}), \
         patch.object(jobs_module, "run_extract_keywords", return_value={}), \
         patch.object(jobs_module, "run_generate_report", return_value={"output_path": "x.md"}) as mock_report:

        result = jobs_module.run_daily_pipeline()

    mock_real_estate.assert_called_once()
    mock_report.assert_called_once()
    assert "error" in result["real_estate"]


def test_daily_pipeline_still_runs_report_even_if_law_collection_fails():
    """LAW_API_KEY 미설정 등으로 run_collect_law가 에러 dict를 반환해도
    (예외를 던지지 않음) 나머지 파이프라인은 그대로 진행되어야 한다."""
    error_result = {"collected": 0, "saved": 0, "skipped": 0, "error": "LAW_API_KEY가 설정되지 않았습니다."}
    with patch.object(jobs_module, "run_collect_dart", return_value={}), \
         patch.object(jobs_module, "run_collect_bond", return_value={}), \
         patch.object(jobs_module, "run_collect_fred", return_value={}), \
         patch.object(jobs_module, "run_collect_news", return_value={}), \
         patch.object(jobs_module, "run_collect_real_estate", return_value={}), \
         patch.object(jobs_module, "run_collect_law", return_value=error_result) as mock_law, \
         patch.object(jobs_module, "run_extract_keywords", return_value={}), \
         patch.object(jobs_module, "run_generate_report", return_value={"output_path": "x.md"}) as mock_report:

        result = jobs_module.run_daily_pipeline()

    mock_law.assert_called_once()
    mock_report.assert_called_once()
    assert "error" in result["law"]


def test_daily_pipeline_sends_email_when_smtp_and_recipients_configured():
    from contextlib import ExitStack

    with ExitStack() as stack:
        for p in _patch_pipeline_steps():
            stack.enter_context(p)
        stack.enter_context(patch.object(jobs_module.settings, "smtp_host", "smtp.example.com"))
        stack.enter_context(patch.object(jobs_module.settings, "report_email_to", ["a@example.com"]))
        mock_send = stack.enter_context(patch.object(jobs_module, "send_report_email"))

        jobs_module.run_daily_pipeline()

    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["markdown_content"] == "# 리포트"
    assert mock_send.call_args.kwargs["to_addrs"] == ["a@example.com"]


def test_pipeline_skips_email_when_smtp_not_configured():
    from contextlib import ExitStack

    with ExitStack() as stack:
        for p in _patch_pipeline_steps():
            stack.enter_context(p)
        stack.enter_context(patch.object(jobs_module.settings, "smtp_host", ""))
        stack.enter_context(patch.object(jobs_module.settings, "report_email_to", ["a@example.com"]))
        mock_send = stack.enter_context(patch.object(jobs_module, "send_report_email"))

        jobs_module.run_weekly_pipeline()

    mock_send.assert_not_called()


def test_pipeline_skips_email_when_no_recipients_configured():
    from contextlib import ExitStack

    with ExitStack() as stack:
        for p in _patch_pipeline_steps():
            stack.enter_context(p)
        stack.enter_context(patch.object(jobs_module.settings, "smtp_host", "smtp.example.com"))
        stack.enter_context(patch.object(jobs_module.settings, "report_email_to", []))
        mock_send = stack.enter_context(patch.object(jobs_module, "send_report_email"))

        jobs_module.run_monthly_pipeline()

    mock_send.assert_not_called()


def test_pipeline_continues_when_email_send_fails():
    """이메일 발송이 실패해도(예: SMTP 인증 오류) 파이프라인 자체는 예외 없이 끝나야 한다."""
    from contextlib import ExitStack

    with ExitStack() as stack:
        for p in _patch_pipeline_steps():
            stack.enter_context(p)
        stack.enter_context(patch.object(jobs_module.settings, "smtp_host", "smtp.example.com"))
        stack.enter_context(patch.object(jobs_module.settings, "report_email_to", ["a@example.com"]))
        stack.enter_context(
            patch.object(jobs_module, "send_report_email", side_effect=RuntimeError("SMTP 인증 실패"))
        )

        result = jobs_module.run_daily_pipeline()  # 예외를 던지지 않아야 함

    assert result["report"]["output_path"] == "x.md"
