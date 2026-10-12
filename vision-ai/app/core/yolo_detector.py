"""
사람 탐지 모듈 (YOLO 기반)

이전 버전은 OpenCV 배경차분(MOG2)으로 '움직임'만 감지했는데,
이 방식은 사람과 컨베이어 벨트 자체의 움직임을 구분하지 못하는 근본적 한계가 있었다.
(위험구역 담당자가 MediaPipe 다중 인식에서 겪은 것과 비슷하게, 우리 쪽도 방식 자체의 한계였다)

팀 전체 아키텍처(Vision AI Server = FastAPI + YOLO)에 맞춰 사람 탐지를 YOLO로 교체한다.
이러면 부수적으로 다음 문제들도 구조적으로 해결된다:
  - 벨트 표면의 움직임을 사람으로 오탐하는 문제 (YOLO는 '사람'만 탐지하므로 애초에 발생 안 함)
  - 정지한 사람이 배경으로 흡수되어 감지가 끊기는 문제 (YOLO는 매 프레임 독립적으로 탐지하므로
    '학습된 배경'이라는 개념 자체가 없다 → 가만히 있어도 계속 잡힘)
"""

import logging
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

logger = logging.getLogger("vision_ai.yolo_detector")

COCO_PERSON_CLASS_ID = 0  # YOLO(COCO 데이터셋 기준) 'person' 클래스 번호


@dataclass
class PersonDetection:
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float


class PersonDetector:
    """YOLO 모델을 감싸서, 우리 프로젝트에 필요한 '사람 탐지'만 깔끔하게 제공하는 얇은 래퍼."""

    def __init__(self, model_path: str = "yolo26n.pt", confidence_threshold: float = 0.4):
        """
        model_path: YOLO 가중치 파일. 기본값(yolo26n.pt)은 처음 실행 시 자동 다운로드된다
                    (인터넷 연결 필요, nano 모델이라 가장 가볍고 빠름).
                    YOLO26은 COCO로 사전학습되어 있어 'person' 클래스(0번)를 그대로 쓸 수 있다.
        confidence_threshold: 이 값보다 확신도가 낮은 탐지는 무시한다.
        """
        from ultralytics import YOLO  # 지연 import: 모델 로드가 무거우니 실제로 쓸 때만 로드

        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold

    def detect(self, frame: np.ndarray) -> List[PersonDetection]:
        """프레임 1장에서 사람만 골라서 반환한다 (다른 클래스는 무시)."""
        results = self.model(frame, verbose=False, classes=[COCO_PERSON_CLASS_ID])

        detections = []
        for result in results:
            for box in result.boxes:
                conf = float(box.conf[0])
                if conf < self.confidence_threshold:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    PersonDetection(
                        bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                        confidence=conf,
                    )
                )
        return detections
