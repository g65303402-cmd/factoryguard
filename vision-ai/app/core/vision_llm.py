"""
Vision LLM 분석 모듈 (OpenAI Vision API)

주의: 이 모듈은 '실시간 상시 호출'이 아니라 '이벤트 발생 시에만' 호출한다.
CCTV 프레임을 24시간 계속 Vision API에 보내면 비용이 감당 안 되므로,
danger_zone_detector 등 로컬 경량 감지에서 이벤트가 잡혔을 때만
그 순간의 프레임을 캡처해서 Vision LLM에 상황 설명을 요청하는 구조다.
(기획서 2-3 핵심기능 ③ 및 이전 논의에서 확정한 방식)

상용화 단계에서는 Qwen2-VL 등 오픈모델로 전환할 수 있도록
OpenAI 호출 부분만 이 파일에 격리해뒀다 (다른 모듈은 이 클래스의 analyze()만 알면 됨).
"""

import base64
import logging
import os
from typing import Optional
import cv2
import numpy as np
from openai import OpenAI

from app.config import get_openai_api_key

logger = logging.getLogger("vision_ai.vision_llm")

SYSTEM_PROMPT = """당신은 제조업 공장 컨베이어 벨트 안전 모니터링 시스템의 분석 담당 AI다.
CCTV에서 캡처된 이미지를 보고 다음을 한국어로 간결하게 작성하라.

1. 상황 요약 (1~2문장): 누가, 어디서, 무엇을 하고 있는지
2. 위험도 판단: 낮음/중간/높음 중 하나와 이유
3. 근거: 어떤 시각적 단서로 그렇게 판단했는지

과장하지 말고, 이미지에서 실제로 확인 가능한 내용만 서술한다.
사람이 명확히 보이지 않으면 "사람 식별 불가"라고 명시한다."""


class VisionLLMAnalyzer:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        api_key: 직접 넘기면 그 값을 쓰고, 안 넘기면 .env 파일의 OPENAI_API_KEY를 읽는다.
        model: MVP는 gpt-4o-mini(비용 저렴) 기본값. 필요시 gpt-4o로 교체 가능.
        """
        self.client = OpenAI(api_key=api_key or get_openai_api_key())
        self.model = model

    @staticmethod
    def _frame_to_base64(frame: np.ndarray) -> str:
        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError("프레임을 JPEG로 인코딩하지 못했습니다.")
        return base64.b64encode(buffer).decode("utf-8")

    def analyze(self, frame: np.ndarray, context: Optional[str] = None) -> str:
        """
        frame: OpenCV BGR 이미지 (danger_zone_detector가 이벤트를 감지한 그 순간의 프레임)
        context: 추가 맥락 (예: "위험구역 접근 감지, 겹침 비율 12%")
        반환: Vision LLM이 작성한 상황 설명 텍스트
        """
        b64_image = self._frame_to_base64(frame)

        user_text = "이 CCTV 캡처 이미지를 분석해줘."
        if context:
            user_text += f"\n\n감지 시스템이 준 참고 정보: {context}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                            },
                        ],
                    },
                ],
                max_tokens=300,
                temperature=0.2,
            )
            description = response.choices[0].message.content
            logger.info("Vision LLM 분석 완료")
            return description

        except Exception as e:
            logger.error(f"Vision LLM 호출 실패: {e}")
            return f"[분석 실패: Vision LLM 호출 중 오류 발생 - {e}]"
