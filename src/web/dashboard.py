"""생성된 리포트를 브라우저에서 확인할 수 있는 간단한 웹 대시보드.

reports 테이블(report_generator.py가 리포트 생성 시 함께 기록하는 곳)에 저장된 목록을
보여주고, 클릭하면 Markdown 본문을 HTML로 렌더링해서 보여준다. 차트 이미지
(reports_output/charts/*.png)는 정적 파일로 함께 서빙한다.
PROJECT_GUIDELINE.md 7단계(배포)의 "간단한 웹 대시보드" 항목.
"""

import re

import markdown
from flask import Flask, abort, send_from_directory

from config.settings import settings
from src.storage.db import get_session
from src.storage.models import Report

_PERIOD_LABELS = {"daily": "일간", "weekly": "주간", "monthly": "월간", "yearly": "연간"}

# report_template.md.j2가 "charts/파일명.png" 상대경로로 이미지를 참조하는데, 그 상대경로는
# 리포트 .md 파일 기준이다. 대시보드에선 URL 경로가 다르므로(/report/<id>) 절대경로
# (/charts/파일명.png, 아래 chart_image 라우트)로 바꿔서 렌더링한다.
_CHART_SRC_RE = re.compile(r'src="charts/')


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        session = get_session()
        try:
            reports = session.query(Report).order_by(Report.generated_at.desc()).all()
            rows = "".join(
                f'<li><a href="/report/{r.id}">'
                f'{_PERIOD_LABELS.get(r.period_type.value, r.period_type.value)}'
                f' · {r.asset_class.value if r.asset_class else "전체"}'
                f' · {r.period_start.strftime("%Y-%m-%d")} ~ {r.period_end.strftime("%Y-%m-%d")}'
                f' (생성 {r.generated_at.strftime("%Y-%m-%d %H:%M")})</a></li>'
                for r in reports
            )
        finally:
            session.close()
        body = f"<ul>{rows}</ul>" if rows else "<p>생성된 리포트가 없습니다.</p>"
        return f"<h1>금융 AI 에이전트 - 리포트 대시보드</h1>{body}"

    @app.route("/report/<int:report_id>")
    def view_report(report_id):
        session = get_session()
        try:
            report = session.get(Report, report_id)
        finally:
            session.close()
        if report is None:
            abort(404)

        html_body = markdown.markdown(report.content_markdown, extensions=["extra"])
        html_body = _CHART_SRC_RE.sub('src="/charts/', html_body)
        return f'<p><a href="/">&larr; 목록으로</a></p><hr>{html_body}'

    @app.route("/charts/<path:filename>")
    def chart_image(filename):
        return send_from_directory(settings.reports_output_dir / "charts", filename)

    return app
