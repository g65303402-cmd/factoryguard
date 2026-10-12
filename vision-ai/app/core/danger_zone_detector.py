"""
위험구역 접근 감지 (YOLO 사람 탐지 기반)

PersonDetector(yolo_detector.py)가 찾은 사람의 위치(bbox)가
미리 지정한 위험구역(polygon)과 얼마나 겹치는지를 계산해서
'위험구역 접근' 여부를 판단한다.

이전 버전(OpenCV 배경차분)과 인터페이스를 최대한 동일하게 유지했다
(detect()가 반환하는 dict 구조: zone_name, overlap_ratio, bbox).
그래서 event_store, vision_ai_service 등 다른 코드는 거의 손댈 필요가 없다.
"""

import cv2
import numpy as np
from typing import List, Tuple
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont

from app.core.yolo_detector import PersonDetector

Point = Tuple[int, int]

# cv2.putText(cv2.FONT_HERSHEY_SIMPLEX)는 한글을 지원하지 않아 "?????"로 깨져서 나온다.
# 디버그/발표 시연 화면에 한글 라벨(위험구역 이름, 안내 문구)이 정상 표시되도록
# PIL + Windows 기본 한글 폰트(맑은 고딕)로 텍스트만 별도로 그린다.
_KR_FONT_PATH = "C:/Windows/Fonts/malgun.ttf"


@dataclass
class DangerZone:
    """위험구역 정의 - 컨베이어 벨트 하부처럼 위험한 영역을 다각형으로 지정"""
    name: str
    polygon: List[Point]  # [(x1,y1), (x2,y2), ...] 화면 좌표 기준

    def mask(self, frame_shape) -> np.ndarray:
        """이 구역만 흰색(255)인 마스크 생성"""
        h, w = frame_shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        pts = np.array(self.polygon, dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)
        return mask


class DangerZoneDetector:
    def __init__(
        self,
        zones: List[DangerZone],
        overlap_threshold: float = 0.15,
        person_detector: PersonDetector = None,
    ):
        """
        zones: 감시할 위험구역 목록 (컨베이어 벨트 하부 등 여러 곳 지정 가능)
        overlap_threshold: 사람의 bbox 면적 중 몇 %가 구역과 겹치면 '접근'으로 판단할지 (기본 15%)
        person_detector: 주입하지 않으면 기본 YOLO 모델(yolov8n)을 자동 생성한다.
                          테스트 시에는 mock 객체를 넣어서 실제 모델 없이도 로직을 검증할 수 있다.
        """
        self.zones = zones
        self.overlap_threshold = overlap_threshold
        self.person_detector = person_detector or PersonDetector()
        self._zone_masks_cache = {}

    def _get_zone_mask(self, zone: DangerZone, frame_shape) -> np.ndarray:
        key = (zone.name, frame_shape[:2])
        if key not in self._zone_masks_cache:
            self._zone_masks_cache[key] = zone.mask(frame_shape)
        return self._zone_masks_cache[key]

    @staticmethod
    def _bbox_mask(bbox: Tuple[int, int, int, int], frame_shape) -> np.ndarray:
        x, y, w, h = bbox
        mask = np.zeros(frame_shape[:2], dtype=np.uint8)
        mask[max(y, 0):y + h, max(x, 0):x + w] = 255
        return mask

    def detect(self, frame: np.ndarray) -> List[dict]:
        """
        프레임 1장을 분석해서, 위험구역 접근이 감지된 결과 목록을 반환.
        반환 형식: [{"zone_name": str, "overlap_ratio": float, "bbox": (x,y,w,h),
                     "person_confidence": float}, ...]
        아무도 위험구역에 없으면 빈 리스트.

        판단 방식: YOLO로 찾은 사람 한 명 한 명에 대해, 그 사람의 bbox가
        각 위험구역과 얼마나 겹치는지(overlap_ratio = 겹친 픽셀 / 사람 bbox 픽셀)를 계산한다.
        """
        people = self.person_detector.detect(frame)
        results = []

        for person in people:
            person_mask = self._bbox_mask(person.bbox, frame.shape)
            person_pixels = cv2.countNonZero(person_mask)
            if person_pixels == 0:
                continue

            for zone in self.zones:
                zone_mask = self._get_zone_mask(zone, frame.shape)
                overlap = cv2.bitwise_and(person_mask, zone_mask)
                overlap_pixels = cv2.countNonZero(overlap)
                ratio = overlap_pixels / person_pixels

                if ratio >= self.overlap_threshold:
                    results.append({
                        "zone_name": zone.name,
                        "overlap_ratio": round(ratio, 4),
                        "bbox": person.bbox,
                        "person_confidence": round(person.confidence, 4),
                    })

        return results

    def draw_debug(self, frame: np.ndarray, detections: List[dict]) -> np.ndarray:
        """디버그/발표 시연용: 위험구역과 감지 결과를 화면에 그려서 반환"""
        out = frame.copy()
        detected_names = {d["zone_name"] for d in detections}
        texts = []  # (문구, (x, y), color_bgr, font_size) - 마지막에 한 번에 한글로 그림

        for zone in self.zones:
            pts = np.array(zone.polygon, dtype=np.int32)
            color = (0, 0, 255) if zone.name in detected_names else (0, 200, 0)
            cv2.polylines(out, [pts], isClosed=True, color=color, thickness=2)
            texts.append((zone.name, zone.polygon[0], color, 20))

        for d in detections:
            x, y, w, h = d["bbox"]
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 0, 255), 2)
            texts.append((
                f"위험구역 접근 {d['overlap_ratio']*100:.0f}% (사람 확신도 {d['person_confidence']*100:.0f}%)",
                (x, max(y - 10, 20)), (0, 0, 255), 18
            ))

        return self._draw_korean_texts(out, texts)

    @staticmethod
    def _draw_korean_texts(frame: np.ndarray, texts: list) -> np.ndarray:
        """
        texts: [(문구, (x, y), color_bgr, font_size), ...]
        cv2.putText(cv2.FONT_HERSHEY_SIMPLEX)는 한글을 지원하지 않아 "?????"로 깨져서 나온다.
        PIL로 변환해서 한글 텍스트를 그린 뒤 다시 OpenCV(BGR) 배열로 돌려준다.
        폰트 파일을 못 찾으면(비Windows 환경 등) 기본 폰트로 대체하되 한글은 깨질 수 있다.

        사람이 여러 명 붙어 있으면 라벨끼리 겹쳐서 안 읽히는 문제가 있어서,
        이미 그린 라벨과 겹치면 아래로 한 줄씩 밀어서 그리고(겹침 방지),
        가독성을 위해 텍스트 뒤에 배경 박스도 깔아준다.
        """
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        placed_boxes: list = []

        for text, (x, y), color_bgr, font_size in texts:
            try:
                font = ImageFont.truetype(_KR_FONT_PATH, font_size)
            except OSError:
                font = ImageFont.load_default()

            box = draw.textbbox((x, y), text, font=font)
            while any(DangerZoneDetector._boxes_overlap(box, placed) for placed in placed_boxes):
                y += (box[3] - box[1]) + 6  # 겹치면 한 줄 아래로
                box = draw.textbbox((x, y), text, font=font)
            placed_boxes.append(box)

            pad = 2
            draw.rectangle(
                (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad),
                fill=(0, 0, 0),
            )
            color_rgb = (color_bgr[2], color_bgr[1], color_bgr[0])
            draw.text((x, y), text, font=font, fill=color_rgb)

        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    @staticmethod
    def _boxes_overlap(a: tuple, b: tuple) -> bool:
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        return not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0)
