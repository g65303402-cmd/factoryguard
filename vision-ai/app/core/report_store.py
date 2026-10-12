"""
사후 리포트 데이터 모델 및 저장소

DB 설계의 INCIDENT_REPORT 컬렉션에 대응한다.
RAG 담당자 RAG API(/rag/report)가 준 법령 근거 + LLM이 문장화한 최종 리포트 텍스트를
하나로 묶어서 저장한다.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


@dataclass
class IncidentReport:
    event_id: str  # 이 리포트가 어떤 DetectionEvent에서 생성됐는지 (EVENT 컬렉션과 연결)
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    report_text: str = ""                       # LLM이 문장화한 최종 리포트 본문
    rag_sources: List[dict] = field(default_factory=list)  # RAG API가 준 근거(출처·페이지 등), LLM이 지어내지 않도록 그대로 보존
    generation_failed: bool = False              # RAG/LLM 호출 실패 시 True (사유는 report_text에 기록)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d


class ReportStore:
    """IncidentReport를 로컬 JSON Lines로 축적 (EventStore와 동일한 패턴)"""

    def __init__(self, storage_path: str = "data/reports.jsonl"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.touch()

    def add(self, report: IncidentReport) -> None:
        with open(self.storage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")

    def get_by_event_id(self, event_id: str) -> Optional[dict]:
        with open(self.storage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record["event_id"] == event_id:
                    return record
        return None

    def get_all(self, limit: Optional[int] = None) -> List[dict]:
        reports = []
        with open(self.storage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    reports.append(json.loads(line))
        reports.sort(key=lambda r: r["created_at"], reverse=True)
        return reports[:limit] if limit else reports
