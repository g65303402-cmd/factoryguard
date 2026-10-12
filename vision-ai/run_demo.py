"""
Vision AI 데모 실행 스크립트

주의: sample_data/demo.mp4는 실제 사람이 아니라 도형(사각형)으로 사람을 흉내낸
합성 영상이다. YOLO는 실제 사람 형태를 학습한 모델이라 이 도형을 사람으로
인식하지 못한다. 즉 --webcam 없이 실행하면 감지 결과가 0건으로 나오는 게 정상이다.
실제 탐지 동작을 확인하려면 --webcam으로 진짜 사람을 비춰보거나,
tests/manual_yolo_integration_test.py로 실제 사진을 테스트할 것.

사용법:
  python run_demo.py                    # (참고용) 합성 영상 - YOLO는 감지 못 함, 파이프라인 동작만 확인
  python run_demo.py --webcam           # 실제 웹캠 사용 (진짜 탐지 확인은 이걸로)
  python run_demo.py --webcam --vision-llm   # 웹캠 + Vision LLM까지 사용 (key/openai_api_key 필요)
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.core.zone_config import load_zones
from app.vision_ai_service import VisionAIService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vision-llm", action="store_true", help="Vision LLM 분석 활성화")
    parser.add_argument("--webcam", action="store_true", help="웹캠(장치 0) 사용")
    parser.add_argument("--max-frames", type=int, default=160, help="처리할 최대 프레임 수")
    args = parser.parse_args()

    if not args.webcam:
        print(
            "⚠️  합성 데모 영상은 실제 사람이 아니라 도형이라 YOLO가 인식하지 못합니다.\n"
            "   감지 결과 0건이 정상입니다. 실제 탐지를 보려면 --webcam 옵션을 쓰세요.\n"
        )

    # 위험구역: zones_config.json이 있으면 그걸 쓰고, 없으면 데모 영상 기준 기본값을 쓴다.
    # 실제 웹캠 화면에 맞는 좌표는 위험구역 담당자의 위험구역 그리기 도구로 만들 것 (파일 공유).
    zones = load_zones()

    source = 0 if args.webcam else "sample_data/demo.mp4"

    def on_event(event):
        # Backend(FastAPI) 완성되면 여기서 requests.post(...)로 전송하도록 교체하면 됨
        print(f"  >>> [콜백] 이벤트 발생 알림: {event.event_type.value} (id={event.event_id[:8]})")

    service = VisionAIService(
        source=source,
        zones=zones,
        use_vision_llm=args.vision_llm,
        on_event=on_event,
        analysis_cooldown_sec=5.0,
    )

    print(f"=== Vision AI 데모 시작 (source={source}, vision_llm={args.vision_llm}) ===\n")
    service.run(max_frames=args.max_frames, frame_interval_sec=0.0)

    print("\n=== 감지 이력 (최근 5건) ===")
    for e in service.get_history(limit=5):
        desc = e.get("vision_llm_description")
        print(f"- {e['timestamp']} | {e['event_type']} | severity={e['severity']} | "
              f"confidence={e['confidence']:.3f}")
        if desc:
            print(f"    Vision LLM 분석: {desc[:80]}...")

    print("\n=== 유형별 통계 ===")
    print(json.dumps(service.get_stats(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
