"""scripts/run_scheduler.py 테스트 (실제 스케줄러 루프는 돌리지 않고 설정/즉시실행만 검증)."""

import sys
from unittest.mock import MagicMock, patch

import scripts.run_scheduler as scheduler_script


def test_run_now_triggers_specified_pipeline_once():
    mock_scheduler_instance = MagicMock()
    mock_scheduler_instance.start.side_effect = KeyboardInterrupt

    with patch.object(scheduler_script, "run_daily_pipeline") as mock_daily, \
         patch.object(scheduler_script, "BlockingScheduler", return_value=mock_scheduler_instance):
        sys.argv = ["run_scheduler.py", "--run-now", "daily"]
        scheduler_script.main()

    mock_daily.assert_called_once()


def test_main_registers_four_jobs_with_expected_ids():
    mock_scheduler_instance = MagicMock()
    mock_scheduler_instance.start.side_effect = KeyboardInterrupt

    with patch.object(scheduler_script, "BlockingScheduler", return_value=mock_scheduler_instance):
        sys.argv = ["run_scheduler.py"]
        scheduler_script.main()

    job_ids = [call.kwargs["id"] for call in mock_scheduler_instance.add_job.call_args_list]
    assert job_ids == ["daily_pipeline", "weekly_pipeline", "monthly_pipeline", "yearly_pipeline"]


def test_main_exits_gracefully_on_keyboard_interrupt(capsys):
    mock_scheduler_instance = MagicMock()
    mock_scheduler_instance.start.side_effect = KeyboardInterrupt

    with patch.object(scheduler_script, "BlockingScheduler", return_value=mock_scheduler_instance):
        sys.argv = ["run_scheduler.py"]
        scheduler_script.main()  # 예외가 밖으로 전파되지 않아야 함 (테스트가 여기까지 오면 성공)

    captured = capsys.readouterr()
    assert "종료합니다" in captured.out


def test_main_calls_scheduler_shutdown_on_keyboard_interrupt():
    """Ctrl+C 시 scheduler.shutdown()을 호출해야 백그라운드 스레드가 남아 프로세스가
    안 꺼지는 문제(실제로 겪었던 버그)가 재발하지 않는다."""
    mock_scheduler_instance = MagicMock()
    mock_scheduler_instance.start.side_effect = KeyboardInterrupt

    with patch.object(scheduler_script, "BlockingScheduler", return_value=mock_scheduler_instance):
        sys.argv = ["run_scheduler.py"]
        scheduler_script.main()

    mock_scheduler_instance.shutdown.assert_called_once_with(wait=False)


def test_custom_hours_are_passed_to_cron_triggers():
    """--daily-hour/--weekly-hour로 지정한 시각이 실제 CronTrigger에 반영되는지 확인."""
    mock_scheduler_instance = MagicMock()
    mock_scheduler_instance.start.side_effect = KeyboardInterrupt

    with patch.object(scheduler_script, "BlockingScheduler", return_value=mock_scheduler_instance):
        sys.argv = ["run_scheduler.py", "--daily-hour", "6", "--weekly-hour", "10"]
        scheduler_script.main()

    daily_call = next(
        c for c in mock_scheduler_instance.add_job.call_args_list if c.kwargs["id"] == "daily_pipeline"
    )
    weekly_call = next(
        c for c in mock_scheduler_instance.add_job.call_args_list if c.kwargs["id"] == "weekly_pipeline"
    )
    # CronTrigger는 내부 필드로 시각을 갖고 있으므로 문자열 표현에 시각이 포함되는지로 간접 확인한다
    assert "hour='6'" in str(daily_call.args[1]) or "hour=6" in repr(vars(daily_call.args[1]))
    assert "hour='10'" in str(weekly_call.args[1]) or "hour=10" in repr(vars(weekly_call.args[1]))
