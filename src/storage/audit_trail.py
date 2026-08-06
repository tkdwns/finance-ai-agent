"""금융 규제 준수 및 AI 추론 이력 보관을 위한 Audit Trail 기록기 모듈."""

from datetime import datetime
import json
from pathlib import Path
from typing import Any


class AuditTrailLogger:
    """Agent의 모든 추론, 도구 호출, 관찰 내역을 타임스탬프와 함께 보관하는 감사 기록기."""

    def __init__(self, log_path: str = "reports_output/audit_trail.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self, query_id: str, role: str, action: str, details: dict[str, Any]
    ) -> dict[str, Any]:
        """단일 감사 이력 이벤트를 생성하고 파일에 기록한다."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "query_id": query_id,
            "role": role,
            "action": action,
            "details": details,
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record

    def get_history(self, query_id: str | None = None) -> list[dict[str, Any]]:
        """저장된 감사 이력 로그를 조회한다."""
        if not self.log_path.exists():
            return []

        results = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    if query_id is None or rec.get("query_id") == query_id:
                        results.append(rec)
        return results


# 전역 기본 감사 기록기 인스턴스
global_audit_logger = AuditTrailLogger()
