"""
API 키 로더

OpenAI API 키를 'key/openai_api_key' 파일에서 읽어온다.
이 파일 안에는 접두어("OPENAI_API_KEY=" 같은 것) 없이,
발급받은 키 값 딱 한 줄만 넣으면 된다.

    key/openai_api_key 파일 내용 예시:
    sk-abc123...

사용법:
    from app.config import get_openai_api_key
    key = get_openai_api_key()
"""

import logging
from pathlib import Path

logger = logging.getLogger("vision_ai.config")

DEFAULT_KEY_PATH = "key/openai_api_key"
_PLACEHOLDER_PREFIXES = ("sk-여기에", "여기에", "sk-실제", "sk-발급받은")


def get_openai_api_key(key_path: str = DEFAULT_KEY_PATH) -> str:
    """
    key_path 파일을 읽어서 키 값(공백/줄바꿈 제거)을 반환한다.
    파일이 없거나, 템플릿 값이 그대로 남아있으면 무엇을 해야 하는지
    구체적으로 알려주는 에러를 던진다 (OpenAI 라이브러리가 던지는
    애매한 인증 에러만 보고 팀원이 헤매지 않도록 하기 위함).
    """
    path = Path(key_path)

    if not path.exists():
        raise RuntimeError(
            f"'{key_path}' 파일이 없습니다.\n"
            f"  1) '{key_path}.example' 파일을 복사해서 '{key_path}' 파일을 만드세요.\n"
            f"     cp {key_path}.example {key_path}\n"
            f"  2) 그 파일을 열어서 발급받은 키 값만 한 줄로 붙여넣으세요 (예: sk-abc123...)."
        )

    key = path.read_text(encoding="utf-8").strip()

    if not key or key.startswith(_PLACEHOLDER_PREFIXES):
        raise RuntimeError(
            f"'{key_path}' 파일에 실제 키 값이 채워지지 않았습니다. "
            f"발급받은 키로 파일 내용을 바꿔주세요."
        )

    logger.info(f"'{key_path}'에서 API 키 로드 완료")
    return key
