"""
감지 이력 축적 및 유형별 통계 (기획서 2-3 핵심기능 ②)

MVP 단계에서는 로컬 JSON 파일로 이력을 쌓는다.
실제 서비스에서는 Backend(백엔드 담당자)의 FastAPI가 MongoDB EVENT 컬렉션에 저장하지만,
Vision AI 모듈 단독으로도 테스트/시연이 가능하도록 로컬 저장소를 기본 제공한다.

Backend와 연동할 때는:
  1) EventStore 대신 이 이벤트를 API로 POST 하는 방식으로 교체하거나
  2) EventStore.add()를 override해서 requests.post(...)로 바꾸면 된다.
인터페이스(add/get_history/get_stats)는 그대로 유지하면 되므로 교체 비용이 낮다.
"""

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from app.models.event import DetectionEvent, EventType

# 타임스탬프는 UTC로 저장되지만(event.py 참고), 야간(00~06시) 판정은
# 실제 근무지 기준인 한국 시간(KST, UTC+9)으로 봐야 한다.
# 이 변환 없이는 낮에 발생한 이벤트도 UTC 기준으로 새벽대에 걸려
# "야간 사고"로 잘못 집계된다.
KST = timezone(timedelta(hours=9))


class EventStore:
    def __init__(self, storage_path: str = "data/events.jsonl"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.touch()

    def add(self, event: DetectionEvent) -> None:
        """이벤트 1건을 이력에 추가 (append-only, JSON Lines 형식)"""
        with open(self.storage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def get_history(
        self,
        limit: Optional[int] = None,
        event_type: Optional[EventType] = None,
    ) -> List[dict]:
        """감지 이력 조회. limit=최근 N건, event_type으로 필터링 가능"""
        events = []
        with open(self.storage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if event_type and record["event_type"] != event_type.value:
                    continue
                events.append(record)

        events.sort(key=lambda e: e["timestamp"], reverse=True)
        return events[:limit] if limit else events

    def get_stats(self) -> dict:
        """
        위험 유형별 발생 빈도 통계 (기획서 '유형별 통계' 카드에 대응)
        관리자 대시보드가 이 결과를 그대로 차트로 그릴 수 있는 형태로 반환.
        """
        history = self.get_history()
        type_counter = Counter(e["event_type"] for e in history)
        severity_counter = Counter(e["severity"] for e in history)

        # 시간대별 분포 (0~23시, KST 기준) - 야간 집중도를 보여주는 지표 (뚜안·김용균·SPC삼립 사고가 모두 새벽)
        hour_counter = Counter()
        for e in history:
            ts = datetime.fromisoformat(e["timestamp"]).astimezone(KST)
            hour_counter[ts.hour] += 1

        return {
            "total_events": len(history),
            "by_type": dict(type_counter),
            "by_severity": dict(severity_counter),
            "by_hour": dict(sorted(hour_counter.items())),
            "night_shift_ratio": self._night_ratio(hour_counter),
        }

    @staticmethod
    def _night_ratio(hour_counter: Counter) -> float:
        """00~06시(KST) 사이 발생 비율 - 기획서 근거(야간·단독 작업 위험)와 연결되는 지표"""
        total = sum(hour_counter.values())
        if total == 0:
            return 0.0
        night = sum(v for h, v in hour_counter.items() if 0 <= h < 6)
        return round(night / total, 3)
