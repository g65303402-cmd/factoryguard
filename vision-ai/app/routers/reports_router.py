"""
사고 리포트 라우터

기존 /reports/analyze 는 그대로 두고,
새 엔드포인트 /reports/analyze-with-legal-basis 를 추가한다
(RAG 법령 근거까지 같이 받고 싶을 때 이걸 호출).

(원본은 서버 ai_server/app/routers/reports_router.py 를 기반으로 확장함.
 서버에서 실제로 다운로드한 파일로 재확인 완료: accident_report_service.py는
 app/services/ 바로 밑에 있음. import 경로 그대로 사용.)
"""

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.services.accident_report_service import analyze_accident, generate_report_with_legal_basis


router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)


ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _validate_and_save_upload(image: UploadFile, image_bytes: bytes) -> str:
    """공통 검증 + 임시파일 저장 (기존 /analyze 로직과 동일)"""
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="JPEG, PNG, WEBP 형식의 이미지만 업로드할 수 있습니다.",
        )

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="업로드된 이미지가 비어 있습니다.",
        )

    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="이미지 크기는 10MB 이하여야 합니다.",
        )

    suffix = Path(image.filename or "image.jpg").suffix or ".jpg"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(image_bytes)
        return temp_file.name


@router.post("/analyze")
async def analyze_accident_report(
    image: UploadFile = File(...),
):
    """
    사고 이미지를 업로드받아 Vision LLM으로 분석합니다. (기존 엔드포인트, 변경 없음)
    """
    image_bytes = await image.read()
    temp_path = None

    try:
        temp_path = _validate_and_save_upload(image, image_bytes)

        report = await run_in_threadpool(
            analyze_accident,
            temp_path,
            image.content_type,
        )

        return {
            "success": True,
            "filename": image.filename,
            "report": report,
        }

    except HTTPException:
        raise

    except Exception as exc:
        print(f"[accident-report] error: {exc}")

        raise HTTPException(
            status_code=500,
            detail="사고 이미지 분석 중 오류가 발생했습니다.",
        ) from exc

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/analyze-with-legal-basis")
async def analyze_accident_report_with_legal_basis(
    image: UploadFile = File(...),
):
    """
    사고 이미지를 업로드받아 Vision LLM 분석 + RAG 법령 근거를 함께 반환합니다.
    RAG 서버(백엔드 담당자)가 꺼져있어도 Vision 분석 결과는 정상 반환되고,
    legal_basis/recommended_action만 빈 값으로 나옵니다 (rag_available=False로 확인 가능).
    """
    image_bytes = await image.read()
    temp_path = None

    try:
        temp_path = _validate_and_save_upload(image, image_bytes)

        result = await run_in_threadpool(
            generate_report_with_legal_basis,
            temp_path,
            image.content_type,
        )

        return {
            "success": True,
            "filename": image.filename,
            **result,
        }

    except HTTPException:
        raise

    except Exception as exc:
        print(f"[accident-report] error: {exc}")

        raise HTTPException(
            status_code=500,
            detail="사고 이미지 분석 중 오류가 발생했습니다.",
        ) from exc

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
