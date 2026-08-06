"""
리포트에 삽입할 추이 차트(PNG) 생성 모듈.

데이터가 없거나 추이를 그릴 만큼(2건 이상) 충분하지 않으면 차트를 만들지 않고
None을 반환한다 — 호출부(report_generator.py)는 이 경우 이미지 삽입을 생략한다.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # GUI 없는 서버/스크립트 환경에서도 동작하도록
import matplotlib.pyplot as plt

from src.storage.queries import IndicatorPoint, TransactionPoint

# matplotlib 기본 폰트(DejaVu Sans)는 한글 글리프가 없어 제목/범례가 네모(□)로 깨진다.
# Windows에 기본 내장된 맑은 고딕으로 지정 (해당 폰트가 없는 환경이면 경고만 뜨고
# 기본 폰트로 조용히 대체된다 — 깨질 뿐 에러는 아니다).
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False  # 한글 폰트 사용 시 마이너스 기호 깨짐 방지


# 지표별 선 색깔을 구분하기 위한 색상 순환. matplotlib 기본 팔레트("tab10")를 그대로 사용.
_COLOR_CYCLE = plt.get_cmap("tab10").colors


def generate_bond_charts(points: list[IndicatorPoint], output_dir: str, filename_prefix: str) -> list[tuple[str, str]]:
    """지표별로 개별 PNG 파일을 하나씩 생성한다.

    여러 지표를 한 이미지에 합성하면(서브플롯 격자) 리포트에서 각 그래프가 작고
    흐릿하게 보인다는 피드백에 따라, 지표마다 독립된 PNG로 저장한다(리포트 쪽에서
    3열 격자로 배치). 기준금리처럼 기간 내 값이 1건뿐인 지표도(월별 갱신이라 변동이
    없으면 이렇게 됨) 점 하나짜리 그래프로라도 표시한다 — 예전에는 2건 미만이면
    통째로 제외해 그래프가 사라지는 문제가 있었음.

    Returns:
        (지표명, 파일명) 튜플 리스트. 지표별로 다른 선 색깔을 tab10 팔레트에서 순서대로 배정한다.
    """
    grouped: dict[str, list[IndicatorPoint]] = {}
    for p in points:
        grouped.setdefault(p.indicator_name, []).append(p)

    results: list[tuple[str, str]] = []
    for i, (name, series) in enumerate(grouped.items()):
        series_sorted = sorted(series, key=lambda p: p.date)
        color = _COLOR_CYCLE[i % len(_COLOR_CYCLE)]

        fig, ax = plt.subplots(figsize=(5, 3.5))
        ax.plot(
            [p.date for p in series_sorted], [p.value for p in series_sorted],
            marker="o", color=color,
        )
        ax.set_ylabel(series_sorted[0].unit)
        ax.set_title(name)
        ax.tick_params(axis="x", labelrotation=30)
        fig.tight_layout()

        chart_filename = f"{filename_prefix}_{i}.png"
        _save(fig, output_dir, chart_filename)
        results.append((name, chart_filename))

    return results


def generate_real_estate_chart(points: list[TransactionPoint], output_dir: str, filename: str) -> str | None:
    """지역별 월평균 거래가 추이를 선 그래프로 PNG에 저장한다."""
    monthly: dict[tuple[str, str], list[float]] = {}
    for p in points:
        key = (p.region, p.transaction_date.strftime("%Y-%m"))
        monthly.setdefault(key, []).append(p.transaction_price)

    if len(monthly) < 2:
        return None

    by_region: dict[str, list[tuple[str, float]]] = {}
    for (region, year_month), prices in monthly.items():
        by_region.setdefault(region, []).append((year_month, sum(prices) / len(prices)))

    fig, ax = plt.subplots(figsize=(8, 4))
    for region, series in by_region.items():
        series_sorted = sorted(series, key=lambda s: s[0])
        ax.plot([s[0] for s in series_sorted], [s[1] for s in series_sorted], marker="o", label=region)

    ax.set_ylabel("만원")
    ax.set_title("지역별 월평균 아파트 거래가 추이")
    ax.legend()
    fig.autofmt_xdate()

    _save(fig, output_dir, filename)
    return filename


def _save(fig, output_dir: str, filename: str) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    fig.savefig(Path(output_dir) / filename, bbox_inches="tight")
    plt.close(fig)
