"""
위험구역 설정 로더

위험구역 담당자(실시간 감지 트리거 파트)의 위험구역 그리기 도구가 저장하는 형식을 그대로 읽는다.
같은 좌표 파일을 두 파트가 공유해서 써야, "정지 판단"과 "사후 기록 판단"이
서로 다른 위험구역 기준으로 어긋나는 일이 없다.

위험구역 담당자 쪽 저장 형식 (2026-07-15 확인):
    [
        {
            "zone_id": "drawn-zone-1",
            "name": "Danger-Zone-1",
            "points": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]],
            "severity": "high",
            "is_normalized": false
        }
    ]

is_normalized가 true면 좌표가 0~1 사이 비율값이라는 뜻으로 보이는데,
아직 그 케이스를 실제로 받아본 적이 없어 정규화 좌표 변환은 구현하지 않았다.
나중에 is_normalized=true인 파일을 받으면 그때 프레임 크기를 곱해서
픽셀 좌표로 바꾸는 로직을 추가해야 한다 (아래 TODO 참고).
"""

import json
import os
from typing import List

from app.core.danger_zone_detector import DangerZone

DEFAULT_CONFIG_PATH = "zones_config.json"

# 데모 영상(sample_data/demo.mp4) 기준 기본 좌표.
# 실제 웹캠/CCTV에서는 반드시 위험구역 담당자 도구로 새로 잡은 zones_config.json을 쓸 것 -
# 화면 구도가 다르면 엉뚱한 곳을 위험구역으로 잘못 지정하게 된다.
DEFAULT_ZONES = [
    DangerZone(name="컨베이어_하부", polygon=[(250, 330), (450, 330), (450, 450), (250, 450)]),
]


def load_zones(config_path: str = DEFAULT_CONFIG_PATH) -> List[DangerZone]:
    """
    config_path가 있으면 그 파일(위험구역 담당자 도구 저장 형식)에서 위험구역 목록을 읽어 반환.
    없으면 기본 좌표(DEFAULT_ZONES)를 반환하면서 안내 메시지를 출력한다.
    """
    if not os.path.exists(config_path):
        print(f"[안내] '{config_path}' 파일이 없어 기본 좌표(데모 영상 기준)를 사용합니다.")
        print(f"       실제 카메라 화면에 맞는 좌표는 위험구역 담당자 위험구역 도구로 만들 것.")
        return DEFAULT_ZONES

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    zones = []
    for z in data:
        if z.get("is_normalized"):
            # TODO: 정규화 좌표(0~1 비율) 케이스는 아직 실제로 안 받아봐서 미구현.
            # 실제로 이 값이 true인 파일이 오면, 프레임 가로/세로 크기를 곱해서
            # 픽셀 좌표로 변환하는 로직을 여기에 추가해야 한다.
            print(f"[경고] '{z.get('name')}' 구역은 is_normalized=true인데 "
                  f"정규화 좌표 변환이 아직 구현되어 있지 않습니다. 이 구역은 건너뜁니다.")
            continue

        zones.append(
            DangerZone(name=z["name"], polygon=[tuple(p) for p in z["points"]])
        )

    print(f"[안내] '{config_path}'에서 위험구역 {len(zones)}개를 불러왔습니다 "
          f"(위험구역 담당자 도구 형식): {[z.name for z in zones]}")
    return zones
