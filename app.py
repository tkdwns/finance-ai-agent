import os
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config.settings import settings
from src.multi_agent import FinancialAgentTeam
from src.storage.audit_trail import global_audit_logger

app = FastAPI(
    title="자율형 금융 AI Agent 웹 서비스 API",
    description="국내외 금융 시장 주가, 공시, 금리, 뉴스를 자율적으로 수집·분석·검증·비판하는 AI 에이전트 대시보드 API",
    version="1.0.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 디렉토리 탑재
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 팀 에이전트 오케스트레이터 인스턴스
agent_team = FinancialAgentTeam()


class QueryRequest(BaseModel):
    query: str
    api_key: str | None = None
    pin: str | None = None


@app.get("/")
async def read_index():
    """메인 대시보드 웹 UI 페이지를 제공한다."""
    index_file = static_dir / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html 파일을 찾을 수 없습니다.")
    return FileResponse(str(index_file))


@app.post("/api/analyze")
async def analyze_financial_query(req: QueryRequest) -> dict[str, Any]:
    """사용자의 금융 질의를 Multi-Agent 팀에 전달하여 자율 분석 보고서를 생성한다."""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="질의 내용을 입력하세요.")

    # 외부 방문자가 본인 API 키를 제공한 경우 동적 적용
    if req.api_key and req.api_key.strip():
        os.environ["OPENAI_API_KEY"] = req.api_key.strip()
        os.environ["GEMINI_API_KEY"] = req.api_key.strip()

    try:
        result = agent_team.run_team_analysis(req.query.strip())
        return {
            "status": "success",
            "query_id": result.get("query_id"),
            "query": result.get("query"),
            "report": result.get("final_report"),
            "final_report": result.get("final_report"),
            "compliance": result.get("compliance"),
            "critic": result.get("critic"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Agent 실행 중 오류 발생: {str(e)}")


@app.get("/api/history")
async def get_audit_history(query_id: str | None = None) -> dict[str, Any]:
    """감사 이력 로그(Audit Trail)를 조회한다."""
    try:
        records = global_audit_logger.get_history(query_id=query_id)
        return {"status": "success", "count": len(records), "history": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"감사 로그 조회 오류: {str(e)}")


@app.get("/api/health")
async def health_check(request: Request, pin: str | None = None) -> dict[str, Any]:
    """웹 서버 상태 및 소유자(핀코드/로컬) 여부를 반환한다."""
    has_env_key = bool(settings.openai_api_key or settings.gemini_api_key or settings.anthropic_api_key)
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local_owner = client_ip in ["127.0.0.1", "localhost", "::1"] and has_env_key
    is_pin_valid = bool(pin and pin.strip() == settings.admin_pin_code)
    is_owner = is_local_owner or is_pin_valid

    return {
        "status": "ok",
        "environment": settings.environment,
        "llm_provider": settings.llm_provider,
        "has_env_key": has_env_key,
        "is_local_owner": is_local_owner,
        "is_pin_valid": is_pin_valid,
        "is_owner": is_owner,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
