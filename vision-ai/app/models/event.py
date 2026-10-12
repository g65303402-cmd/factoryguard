"""
감지 이벤트 데이터 모델

Vision AI가 CCTV에서 감지한 모든 이벤트는 이 구조로 통일해서 다룬다.
Backend(백엔드 담당자, FastAPI)로 전송할 때도 이 스키마를 그대로 JSON 직렬화해서 보내면 된다.
DB(MongoDB)의 EVENT 컬렉션 구조와 1:1로 맞춰뒀다.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid


class EventType(str, Enum):
    """위험 유형 분류 (기획서 3-1 '3중 트리거 감지'의 감지 대상과 매핑)"""
    WORKER_APPROACH = "worker_approach"      # 작업자 접근
    DANGER_ZONE = "danger_zone"              # 위험구역 접근 (핵심 - 뚜안 사건 유형)
    DANGEROUS_POSTURE = "dangerous_posture"  # 위험 자세 (예: 컨베이어에 몸을 기울임)
    FALLEN = "fallen"                        # 쓰러짐
    UNKNOWN = "unknown"                      # 분류 전 임시 상태


class EventSeverity(str, Enum):
    """심각도 - 실시간 정지까지는 아니지만 사후 분석 시 우선순위 판단용"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class DetectionEvent:
    """
    CCTV(Vision AI)가 감지한 단일 이벤트.

    실시간 정지 트리거(제스처·음성·위험구역 접근)는 별도 모듈(위험구역·RAG 담당자 파트)이 담당하고,
    이 이벤트는 '지속 감지 및 이력 축적' 용도로 쌓인다.
    단, danger_zone 감지는 이 모듈에서도 발생 가능하며 이 경우 realtime_trigger=True로 표시해
    실시간 정지 모듈에도 알릴 수 있게 한다.
    """

    event_type: EventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    severity: EventSeverity = EventSeverity.LOW
    confidence: float = 0.0                    # 0.0 ~ 1.0
    camera_id: str = "cam-01"
    zone_name: Optional[str] = None              # 어느 위험구역에서 감지됐는지 (리포트 location 근거)
    frame_path: Optional[str] = None            # 캡처된 프레임 이미지 경로 (사후 리포트용 증거)
    bbox: Optional[tuple] = None                 # (x, y, w, h) 감지 위치 - 있으면 시각화용
    vision_llm_description: Optional[str] = None  # Vision LLM이 분석한 상황 설명 (사고 시에만 채워짐)
    realtime_trigger: bool = False               # True면 실시간 정지 모듈에도 즉시 알림 필요

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        d["event_type"] = self.event_type.value
        d["severity"] = self.severity.value
        return d
