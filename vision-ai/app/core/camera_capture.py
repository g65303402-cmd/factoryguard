"""
CCTV 캡처 모듈 (OpenCV 기반)

해커톤 데모 환경에서는 실제 공장 CCTV가 없으므로,
1) 웹캠 (source=0)
2) 데모용 영상 파일 (source="sample_data/demo.mp4")
둘 다 동일한 인터페이스로 쓸 수 있게 만들었다. 발표 때는 2번으로 시연하면 된다.
"""

import cv2
import time
import logging
from typing import Optional, Iterator
import numpy as np

logger = logging.getLogger("vision_ai.camera")


class CameraCapture:
    def __init__(self, source, camera_id: str = "cam-01", loop_video: bool = True):
        """
        source: 0(웹캠 기본 장치) 또는 영상 파일 경로 / RTSP 주소 문자열
        loop_video: 영상 파일일 때 끝나면 처음부터 반복 재생할지 여부 (데모 시연용)
        """
        self.source = source
        self.camera_id = camera_id
        self.loop_video = loop_video
        self._is_file = isinstance(source, str) and not source.startswith("rtsp://")
        self.cap: Optional[cv2.VideoCapture] = None

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            logger.error(f"[{self.camera_id}] 카메라/영상 소스를 열 수 없습니다: {self.source}")
            return False
        logger.info(f"[{self.camera_id}] 캡처 시작: {self.source}")
        return True

    def read_frame(self) -> Optional[np.ndarray]:
        """프레임 1장 읽기. 영상 파일이 끝났고 loop_video=True면 처음으로 되감아 재시도."""
        if self.cap is None:
            raise RuntimeError("open()을 먼저 호출하세요.")

        ok, frame = self.cap.read()
        if not ok:
            if self._is_file and self.loop_video:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self.cap.read()
                if ok:
                    return frame
            logger.warning(f"[{self.camera_id}] 프레임을 읽지 못했습니다.")
            return None
        return frame

    def frame_stream(self, interval_sec: float = 0.0) -> Iterator[np.ndarray]:
        """제너레이터로 프레임을 순서대로 yield. interval_sec만큼 쉬어가며 CPU 부담을 줄인다."""
        while True:
            frame = self.read_frame()
            if frame is None:
                break
            yield frame
            if interval_sec > 0:
                time.sleep(interval_sec)

    def close(self):
        if self.cap is not None:
            self.cap.release()
            logger.info(f"[{self.camera_id}] 캡처 종료")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
