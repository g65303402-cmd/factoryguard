# 프로젝트 보관 구조

이 저장소에는 다시 개발하거나 검색 인덱스를 재현하는 데 필요한 코드, 텍스트 문서,
검수 데이터, 예시 응답을 보관한다.

## GitHub에 보관하는 항목

- `kws_service/`, `rag_service/`: 실행 서비스
- `scripts/`, `tools/`: 인덱스 및 프로젝트 문서 생성 도구
- `docs/scope/`, `docs/rag/`: 범위 정의와 RAG 설계 문서
- `data/rag_chunks_day2/`: 초기 이벤트별 RAG 청크
- `data/conveyor_rag_parent_child_chunks_v1/`: parent-child 청크와 검수 결과
- `data/rag_reviewed/`: 검수 반영 코퍼스
- `examples/rag_search_samples/`: 검색 결과 예시
- `docs/archive/CODEX_HANDOFF.md`: 이전 작업 인수인계 기록

## Google Drive에 보관하는 항목

원본 PDF, HWPX, XLSX, 이미지, 연구 영상, 이전 전달용 ZIP처럼 크기가 크거나
Git diff로 관리하기 어려운 파일은 다음 비공개 Drive 폴더에 보관한다.

- [휴먼3차프로젝트 정리백업 2026-07-24](https://drive.google.com/drive/folders/1r7ALs7z3COhjfhaMFyiNiwyC_kUuyqdL)

가상환경, Python 바이트코드, Hugging Face 모델 캐시는 재설치 가능한 산출물이므로
어느 저장소에도 백업하지 않는다.
