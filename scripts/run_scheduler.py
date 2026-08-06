"""
파이프라인(수집->분석->보고서)을 정해진 시각에 자동으로 실행하는 스케줄러.

이 스크립트를 실행한 상태로 터미널을 계속 켜두면, 지정된 시각마다 자동으로
파이프라인이 돌아간다. Ctrl+C로 종료할 수 있다.

사용법 (프로젝트 루트에서):
    python -m scripts.run_scheduler                    # 기본 스케줄로 실행
    python -m scripts.run_scheduler --run-now daily     # 지금 즉시 일별 파이프라인 1회 실행 후 스케줄 대기
    python -m scripts.run_scheduler --daily-hour 7      # 일별 실행 시각을 7시로 변경

기본 스케줄:
    - 일별 파이프라인: 매일 08:00
    - 주별 파이프라인: 매주 월요일 08:30
    - 월별 파이프라인: 매월 1일 09:00
    - 연별 파이프라인: 매년 1월 1일 09:30

참고: 이 방식은 터미널(또는 서버 프로세스)이 항상 켜져 있어야 동작한다.
컴퓨터를 껐다 켜도 자동으로 켜지길 원하면, Windows 작업 스케줄러에
`python -m scripts.collect_dart ...` 등 개별 명령을 등록하는 방식도 대안이 된다
(README의 '자동화' 섹션 참고).
"""

import argparse
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.scheduler.jobs import (
    run_daily_pipeline,
    run_monthly_pipeline,
    run_weekly_pipeline,
    run_yearly_pipeline,
)

_PIPELINE_NAMES = {
    "daily": "run_daily_pipeline",
    "weekly": "run_weekly_pipeline",
    "monthly": "run_monthly_pipeline",
    "yearly": "run_yearly_pipeline",
}


def _run_with_logging(name: str, func) -> None:
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {name} 파이프라인 실행 시작")
    try:
        func()
    except Exception as e:
        # 스케줄러 스레드에서 예외가 나면 스케줄러 자체가 죽을 수 있어 반드시 잡아서 로그만 남긴다.
        print(f"[오류] {name} 파이프라인 실행 중 예외 발생: {type(e).__name__}: {e}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {name} 파이프라인 실행 종료")


def main():
    parser = argparse.ArgumentParser(description="파이프라인 자동 실행 스케줄러")
    parser.add_argument(
        "--run-now", type=str, default=None, choices=list(_PIPELINE_NAMES.keys()),
        help="스케줄러 시작 전, 지정한 파이프라인을 즉시 1회 실행 (동작 확인용)",
    )
    parser.add_argument("--daily-hour", type=int, default=8, help="일별 파이프라인 실행 시각 (기본 8시)")
    parser.add_argument("--weekly-hour", type=int, default=8, help="주별 파이프라인 실행 시각 (기본 8시, 매주 월요일)")
    args = parser.parse_args()

    if args.run_now:
        # globals()에서 이름으로 조회해야, 테스트 등에서 모듈 속성을 patch했을 때도 반영된다
        # (모듈 로드 시점에 함수 객체를 직접 dict에 담아두면 이후 patch가 반영되지 않는다).
        func = globals()[_PIPELINE_NAMES[args.run_now]]
        _run_with_logging(args.run_now, func)

    scheduler = BlockingScheduler()
    scheduler.add_job(
        lambda: _run_with_logging("일별", run_daily_pipeline),
        CronTrigger(hour=args.daily_hour, minute=0),
        id="daily_pipeline",
    )
    scheduler.add_job(
        lambda: _run_with_logging("주별", run_weekly_pipeline),
        CronTrigger(day_of_week="mon", hour=args.weekly_hour, minute=30),
        id="weekly_pipeline",
    )
    scheduler.add_job(
        lambda: _run_with_logging("월별", run_monthly_pipeline),
        CronTrigger(day=1, hour=9, minute=0),
        id="monthly_pipeline",
    )
    scheduler.add_job(
        lambda: _run_with_logging("연별", run_yearly_pipeline),
        CronTrigger(month=1, day=1, hour=9, minute=30),
        id="yearly_pipeline",
    )

    print("스케줄러 시작. 종료하려면 Ctrl+C를 누르세요.")
    print(f"  - 일별: 매일 {args.daily_hour:02d}:00")
    print(f"  - 주별: 매주 월요일 {args.weekly_hour:02d}:30")
    print("  - 월별: 매월 1일 09:00")
    print("  - 연별: 매년 1월 1일 09:30")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n스케줄러를 종료합니다...")
        # BlockingScheduler는 내부적으로 작업 실행용 스레드를 띄워두는데,
        # shutdown()을 호출하지 않으면 이 스레드가 백그라운드에 남아 프로세스가
        # 종료되지 않는 것처럼 보인다 (Ctrl+C를 눌러도 터미널이 안 꺼지는 원인).
        scheduler.shutdown(wait=False)
        print("종료 완료.")


if __name__ == "__main__":
    main()
