# 🌐 자율형 금융 AI Agent 웹 서비스 구축 가이드라인

현재 CLI(터미널) 환경에서 동작하는 **금융 AI Agent Framework v1.0**을 웹 브라우저에서 대화형 대시보드로 손쉽게 이용할 수 있도록 구축하는 **단계별 가이드라인**입니다.

---

## 🔑 사용자 필요 조치 사항

> **"추가 API 키 발급은 전혀 필요 없습니다!"**
> - 기존 `.env`에 등록된 키를 백엔드 웹 서버가 그대로 활용합니다.
> - 백엔드 웹 서버 라이브러리(`fastapi`, `uvicorn`)만 설치해 주시면 됩니다.

---

## 🏗️ 1. 전체 웹 서비스 아키텍처

- **백엔드 (Backend)**: **FastAPI** (Python 기반 고속 웹 API 서버)
  - 기존 `FinancialAgentTeam.run_team_analysis(query)` 메서드를 HTTP 엔드포인트(`POST /api/analyze`)로 노출
  - 감사 로그(`audit_trail.jsonl`) 및 리포트 전달
- **프론트엔드 (Frontend)**: **HTML5 / Vanilla CSS / Modern JS (대화형 대시보드 UI)**
  - 모던 다크모드 & 글래스모피즘 UI
  - 에이전트 추론 단계(리서처 ➔ 분석가 ➔ 팩트체커 ➔ 비판가) 실시간 프로그레스 바
  - 최종 마크다운 리포트 및 DART 원문 클릭 링크 실시간 렌더링

---

## 🛠️ 2. 구현 단계 (Step-by-Step)

### [Step 1] 백엔드 웹 서버 구축 (`app.py`)
- Python `fastapi`, `uvicorn` 기반으로 웹 API 서비스 구축
- `/api/analyze` (질의 요청), `/api/history` (감사 이력 조회) API 엔드포인트 제공

### [Step 2] 웹 대시보드 인터페이스 구축 (`static/index.html`)
- 프리미엄 금융 대시보드 스타일의 웹 페이지 생성
- "삼성전자 최근 주가 시세와 DART 공시 동향 분석해줘" 원클릭 예시 질문 버튼 제공
- 실시간 리포트 출력 및 감사 로그 모니터링 기능

### [Step 3] 통합 테스트 및 구동
- `python app.py` 실행 후 브라우저 `http://localhost:8000` 접속 테스트

---

## 🚀 승인 및 즉시 착수 안내

승인해 주시면 **`fastapi` 웹 서버(`app.py`) 구축과 프리미엄 웹 대시보드 인터페이스 웹페이지** 작성을 즉시 시작해 드릴 수 있습니다!
