"""
실제 YOLO 모델 통합 테스트 (로컬 전용)

이 스크립트는 여기(개발 샌드박스)에서는 실행이 안 된다 - 네트워크 제한 때문에
YOLO 가중치 파일(yolo26n.pt) 다운로드가 막혀있다.

반드시 실제 인터넷이 되는 팀원 컴퓨터에서 실행해서, 진짜 이미지로 사람이
잘 인식되는지 최종 확인할 것.

사용법:
    python tests/manual_yolo_integration_test.py

첫 실행 시 yolo26n.pt가 자동 다운로드된다.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.yolo_detector import PersonDetector
from app.core.danger_zone_detector import DangerZone, DangerZoneDetector


def main():
    print("=== YOLO 모델 로드 중 (최초 실행 시 자동 다운로드) ===")
    person_detector = PersonDetector()
    print("모델 로드 완료\n")

    # ultralytics 패키지에 내장된 샘플 이미지로 테스트 (실제 사람이 있는 사진)
    from ultralytics.utils import ASSETS
    sample_image_path = str(ASSETS / "bus.jpg")  # 사람 여러 명이 있는 버스 사진

    import cv2
    frame = cv2.imread(sample_image_path)
    if frame is None:
        print(f"샘플 이미지를 찾을 수 없습니다: {sample_image_path}")
        print("대신 본인이 가진 사람 사진 경로를 이 스크립트에 직접 넣어서 테스트하세요.")
        return

    print(f"=== 샘플 이미지({sample_image_path})에서 사람 탐지 테스트 ===")
    people = person_detector.detect(frame)
    print(f"탐지된 사람 수: {len(people)}")
    for i, p in enumerate(people):
        print(f"  사람 {i+1}: bbox={p.bbox}, 확신도={p.confidence:.2f}")

    if len(people) == 0:
        print("\n⚠️ 사람이 하나도 탐지되지 않았습니다. 모델/이미지에 문제가 있을 수 있습니다.")
        return

    print("\n=== 위험구역 겹침 테스트 (이미지 하단 절반을 위험구역으로 가정) ===")
    h, w = frame.shape[:2]
    zone = DangerZone(
        name="테스트_구역",
        polygon=[(0, h // 2), (w, h // 2), (w, h), (0, h)],
    )
    detector = DangerZoneDetector([zone], overlap_threshold=0.15, person_detector=person_detector)
    results = detector.detect(frame)
    print(f"위험구역 접근으로 판단된 사람 수: {len(results)}")
    for r in results:
        print(f"  {r}")

    # 결과 시각화 이미지 저장 (눈으로 확인용)
    debug_frame = detector.draw_debug(frame, results)
    out_path = "sample_data/yolo_test_result.jpg"
    cv2.imwrite(out_path, debug_frame)
    print(f"\n시각화 결과 저장: {out_path} (직접 열어서 박스가 사람 위치에 정확히 그려졌는지 확인하세요)")


if __name__ == "__main__":
    main()
