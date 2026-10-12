"""
현실적 조건(벨트 움직임 + 조명 노이즈) 하에서 위험구역 감지기의 오탐률을 측정한다.

핵심 질문: 사람이 없는 구간(벨트+노이즈만 존재)에서 감지기가 얼마나 오탐하는가?
사람이 있는 구간(160~220프레임)에서는 제대로 감지하는가?
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.camera_capture import CameraCapture
from app.core.danger_zone_detector import DangerZone, DangerZoneDetector

PERSON_FRAME_START = 160
PERSON_FRAME_END = 220

zones = [DangerZone(name="컨베이어_하부", polygon=[(150, 425), (500, 425), (500, 470), (150, 470)])]
detector = DangerZoneDetector(zones)

cam = CameraCapture("sample_data/realistic_test.mp4", loop_video=False)
cam.open()

results = []
frame_idx = 0
while True:
    frame = cam.read_frame()
    if frame is None:
        break
    detections = detector.detect(frame)
    is_person_present = PERSON_FRAME_START <= frame_idx <= PERSON_FRAME_END
    is_detected = len(detections) > 0
    results.append({
        "frame": frame_idx,
        "person_present": is_person_present,
        "detected": is_detected,
        "overlap": detections[0]["overlap_ratio"] if detections else 0.0,
    })
    frame_idx += 1

cam.close()

# 워밍업 구간(배경 모델이 아직 안정화되기 전 처음 30프레임)은 제외하고 분석
warmup = 30
analysis = [r for r in results if r["frame"] >= warmup]

no_person = [r for r in analysis if not r["person_present"]]
with_person = [r for r in analysis if r["person_present"]]

false_positives = sum(1 for r in no_person if r["detected"])
true_positives = sum(1 for r in with_person if r["detected"])

print("=" * 60)
print("현실적 조건 오탐률 테스트 결과")
print("=" * 60)
print(f"워밍업 제외 총 분석 프레임: {len(analysis)}")
print()
print(f"[사람 없는 구간] 총 {len(no_person)}프레임")
print(f"  -> 오탐(사람 없는데 감지됨): {false_positives}프레임 "
      f"({false_positives/len(no_person)*100:.1f}%)")
print()
print(f"[사람 있는 구간] 총 {len(with_person)}프레임")
print(f"  -> 정탐(제대로 감지됨): {true_positives}프레임 "
      f"({true_positives/len(with_person)*100:.1f}%)")
print()

if false_positives > 0:
    max_fp_overlap = max(r["overlap"] for r in no_person if r["detected"])
    print(f"오탐 발생 시 최대 겹침 비율: {max_fp_overlap*100:.1f}%")
    sample_fp = [r for r in no_person if r["detected"]][:5]
    print(f"오탐 샘플 (최대 5개): {sample_fp}")

print("=" * 60)
