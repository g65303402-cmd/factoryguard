# 컨베이어 RAG parent-child 청킹 산출물

## 적용 규칙

- 임베딩 모델: `jhgan/ko-sroberta-multitask`
- 토크나이저: 모델의 `BertTokenizer`, 32,000개 WordPiece 어휘
- child 본문: 최대 100토큰
- 연속 child 겹침: 정확히 20토큰
- 임베딩 입력: `[CLS]`, `[SEP]` 포함 최대 128토큰
- parent: 조문, 검사 항목, 검사 단계, 위험요인·사례 등 의미 단위
- 개인정보 문서는 `privacy`, 산업안전 문서는 `safety_authority` 또는 `safety_guidance` 코퍼스로 분리

## 파일 설명

- `rag_parent_child_chunks.jsonl`: parent와 child를 한 파일에 담은 최종 적재용 JSONL
- `parent_chunks.jsonl`: parent 레코드만 분리
- `child_chunks.jsonl`: 임베딩·FAISS 적재 대상 child만 분리
- `rag_chunk_review.csv`: 사람이 검수하기 위한 전체 child 표
- `rag_chunk_review.xlsx`: 필터·메모가 편하도록 만든 검수용 통합 문서
- `rag_exclusions_dedup.csv`: 문서·페이지 제외 및 중복 제거 근거
- `rag_build_summary.csv`: 문서별 parent/child 수와 토큰 상한 요약
- `chunk_build_config.json`: 청킹 설정과 자동 QA 결과

## 검수 방법

1. `rag_chunk_review.csv` 또는 XLSX의 `청크검수` 시트에서 `텍스트품질=medium/low`를 먼저 확인합니다.
2. `원본파일명`과 `원문페이지`로 정규화 PDF를 대조합니다.
3. 유지할 청크는 `포함여부=Y`, 제외할 청크는 `N`으로 바꾸고 `검수자메모`에 사유를 적습니다.
4. 현행 법적 근거는 `safety_authority`를 우선하며, `historical_reference=true` 청크는 단독 법적 근거로 사용하지 않습니다.
5. `privacy` 코퍼스는 CCTV·개인정보 질의에만 별도 검색하도록 라우팅합니다.

## 주의할 자료

- `11_제조_컨베이어_RAG정규화.pdf`: 다단 편집 원문이라 일부 문장 순서에 수동검수가 필요하며, 구법 복사 구간은 제외했습니다.
- `[2020-산업안전보건인증원-901]_안전검사_컨베이어_매뉴얼_RAG정규화.pdf`: 검사방법 참고용이며, 수치·법적 결론은 현행 별표 11과 교차확인해야 합니다.
- `고용노동부 법령해석(산업안전과-2657)_RAG정규화.pdf`: 2019년 1차 행정해석이므로 현행 기준 확인 없이 단독 인용하지 않습니다.
- `[2022-산업안전보건인증원-369]_9.컨베이어_RAG정규화.pdf`: 통계 도표 OCR 청크는 원본 수치 대조가 필요합니다.
