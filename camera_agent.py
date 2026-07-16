import argparse
import asyncio
import json
import time

import cv2
import websockets


async def run_agent(
    server_url: str,
    camera_id: str,
    camera_index: int,
    fps: float,
    width: int,
    height: int,
):
    websocket_url = f"{server_url.rstrip('/')}/ws/cameras/{camera_id}"
    frame_interval = 1.0 / fps

    while True:
        capture = cv2.VideoCapture(camera_index)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        if not capture.isOpened():
            print("웹캠을 열 수 없습니다. 3초 후 재시도합니다.")
            await asyncio.sleep(3)
            continue

        try:
            print(f"AI 서버 연결 시도: {websocket_url}")

            async with websockets.connect(
                websocket_url,
                max_size=4 * 1024 * 1024,
                ping_interval=20,
                ping_timeout=20,
            ) as websocket:
                await websocket.send(json.dumps({
                    "type": "register",
                    "camera_id": camera_id,
                    "location": "demo-factory",
                }))

                response = await websocket.recv()
                print("서버 응답:", response)

                while True:
                    started_at = time.perf_counter()

                    ok, frame = capture.read()
                    if not ok:
                        raise RuntimeError("웹캠 프레임 읽기 실패")

                    encode_ok, encoded = cv2.imencode(
                        ".jpg",
                        frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 70],
                    )
                    if not encode_ok:
                        continue

                    await websocket.send(encoded.tobytes())

                    elapsed = time.perf_counter() - started_at
                    await asyncio.sleep(max(0, frame_interval - elapsed))

        except Exception as exc:
            print(f"연결 오류: {exc}")
            print("3초 후 다시 연결합니다.")
            await asyncio.sleep(3)
        finally:
            capture.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--server",
        default="wss://ai.j-jandy.com",
        help="AI 서버 주소. 운영 시 wss://ai.j-jandy.com",
    )
    parser.add_argument("--camera-id", default="cam-01")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--fps", type=float, default=5)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()

    asyncio.run(run_agent(
        server_url=args.server,
        camera_id=args.camera_id,
        camera_index=args.camera_index,
        fps=args.fps,
        width=args.width,
        height=args.height,
    ))


if __name__ == "__main__":
    main()
