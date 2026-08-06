"""생성된 Markdown 리포트를 HTML 이메일로 변환해 발송하는 모듈.

리포트 안의 로컬 이미지(charts/*.png)는 상대경로라 이메일 클라이언트가 그대로 불러올
수 없다. 그래서 HTML로 변환한 뒤 이미지들을 인라인 첨부(Content-ID)로 바꿔 넣는다.
report_template.md.j2가 만드는 <table>/<img>/<details> 같은 원본 HTML은 markdown
라이브러리가 그대로 통과시켜주므로 별도 처리 없이도 렌더링된다.
"""

import re
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import markdown

from config.settings import settings

_IMG_SRC_RE = re.compile(r'src="([^"]+\.(?:png|jpg|jpeg|gif))"')


def _markdown_to_html(markdown_content: str) -> str:
    body = markdown.markdown(markdown_content, extensions=["extra"])
    return f"<html><body>{body}</body></html>"


def _embed_images(html: str, chart_dir: str) -> tuple[str, list[MIMEImage]]:
    """상대경로 이미지 src를 cid: 참조로 바꾸고, 실제 파일을 인라인 첨부로 반환한다.

    chart_dir="reports_output/charts"처럼 주어지면, 리포트 안의 "charts/파일명.png"
    상대경로는 그 부모 디렉터리(reports_output/) 기준으로 풀어서 실제 파일을 찾는다.
    """
    images: list[MIMEImage] = []
    chart_base = Path(chart_dir).parent

    def _replace(match: re.Match) -> str:
        rel_path = match.group(1)
        file_path = chart_base / rel_path
        if not file_path.is_file():
            return match.group(0)
        cid = file_path.name
        with open(file_path, "rb") as f:
            img = MIMEImage(f.read())
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline", filename=cid)
        images.append(img)
        return f'src="cid:{cid}"'

    return _IMG_SRC_RE.sub(_replace, html), images


def send_report_email(
    subject: str,
    markdown_content: str,
    to_addrs: list[str],
    chart_dir: str | None = None,
) -> None:
    """리포트를 HTML 이메일로 변환해 발송한다.

    SMTP_HOST 미설정이나 수신자 누락은 "조용히 스킵"하지 않고 예외를 던진다 — 호출부가
    발송 가능 여부를 먼저 확인하도록 강제해, "보냈다고 생각했는데 안 갔다"는 문제를 막는다.
    """
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST가 설정되지 않았습니다. .env 파일을 확인하세요 (.env.example 참고).")
    if not to_addrs:
        raise RuntimeError("수신자(to_addrs)가 비어 있습니다. --to 또는 .env의 REPORT_EMAIL_TO를 설정하세요.")

    html = _markdown_to_html(markdown_content)
    images: list[MIMEImage] = []
    if chart_dir:
        html, images = _embed_images(html, chart_dir)

    from_addr = settings.report_email_from or settings.smtp_user

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg.attach(MIMEText(html, "html", "utf-8"))
    for img in images:
        msg.attach(img)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.ehlo()
        if server.has_extn("STARTTLS"):  # 내부 릴레이 등 TLS 미지원 서버도 있어 조건부로 호출
            server.starttls()
            server.ehlo()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(from_addr, to_addrs, msg.as_string())
