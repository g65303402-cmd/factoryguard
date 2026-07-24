# Codex 인수인계 — 컨베이어 위험감지·정지 RAG 프로젝트

## 1. 프로젝트 목표

산업현장 Vision/KWS 위험감지 이벤트를 받아 컨베이어 정지 판단과 관련 안전근거를 검색하고, 검색 결과를 근거로 리포트를 생성하는 프로젝트다.

예정된 전체 흐름은 다음과 같다.

1. Vision 또는 KWS가 위험 이벤트 생성
2. 이벤트 메타데이터를 검색 질의로 변환
3. FAISS에서 관련 child 청크 검색
4. child의 `parent_id`로 의미 단위 parent 확장
5. 현행 법령·검사기준을 우선하여 안전근거 구성
6. 위험 이벤트·조치·법적 근거가 포함된 리포트 생성
7. KWS 키워드 및 위험 태그와 검색 결과 연결

현재까지는 PDF 정규화와 parent-child 청킹까지 완료했다. 임베딩, FAISS 인덱싱, 이벤트 검색 연결, 리포트 생성, KWS 연결은 아직 구현하지 않았다.

## 2. 사용자와 확정한 결정

- 이벤트 메타데이터 값은 사용자가 당분간 임의 방식으로 만들고, 추후 팀 기준에 맞게 통폐합한다.
- 원본 PDF 대신 OCR·텍스트 추출·정리를 마친 `_RAG정규화.pdf`만 RAG 자료로 사용한다.
- `찐찐최종.pdf`는 기획서이므로 RAG 검색 코퍼스에 넣지 않는다.
- `00_정규화_문서목록.txt`는 목록 문서이므로 RAG 본문에 넣지 않는다.
- 산업안전 자료와 개인정보/CCTV 자료는 같은 검색 인덱스에서 무조건 섞지 않는다.
  - `safety_authority`: 현행 법·부령·고시·검사기준
  - `safety_guidance`: 매뉴얼·교육자료·점검표·과거 행정해석
  - `privacy`: 개인정보 보호법/CCTV 전용
- 현행 법적 답변은 `safety_authority`를 우선한다.
- `historical_reference=true` 자료는 단독 법적 근거로 사용하지 않는다.

## 3. 현재 사용 중인 정규화 문서

RAG 청킹 대상은 다음 10개다. 파일명은 사용자가 프로젝트 소스에 넣은 이름 그대로 유지했다.

1. `[별표 11] 컨베이어 검사기준(제24조 관련)(안전검사 고시)_RAG정규화.pdf`
2. `11_제조_컨베이어_RAG정규화.pdf`
3. `안전검사 절차에 관한 고시(고용노동부고시)(제2026-50호)(20260626)_RAG정규화.pdf`
4. `안전검사 고시(고용노동부고시)(제2026-49호)(20260626)_RAG정규화.pdf`
5. `산업안전보건법(법률)(제21374호)(20260601)_RAG정규화.pdf`
6. `[2020-산업안전보건인증원-901]_안전검사_컨베이어_매뉴얼_RAG정규화.pdf`
7. `고용노동부 법령해석(산업안전과-2657)_RAG정규화.pdf`
8. `개인정보 보호법(법률)(제20897호)(20251002)_CCTV별도_RAG정규화.pdf`
9. `산업안전보건기준에 관한 규칙(고용노동부령)(제00450호)(20260302)_RAG정규화.pdf`
10. `[2022-산업안전보건인증원-369]_9.컨베이어_RAG정규화.pdf`

제외 문서:

- `찐찐최종.pdf`: 프로젝트 기획서
- `00_정규화_문서목록.txt`: 문서 목록·메타자료

## 4. 확정 청킹 규칙

```text
child_chunk_size_tokens = 100
child_chunk_overlap_tokens = 20
parent_chunk_size = 의미 단위
embedding_model = jhgan/ko-sroberta-multitask
embedding_model_max_seq_length = 128
```

토큰은 문자수 추산이 아니라 모델의 실제 `BertTokenizer`/WordPiece 어휘 32,000개를 사용해 계산했다.

- child 본문 토큰: 특수토큰 제외 최대 100
- 임베딩 입력: `[CLS]`, `[SEP]` 포함 최대 128
- 연속 child: 앞 청크 마지막 20토큰과 다음 청크 첫 20토큰이 정확히 일치
- `embed_text`: 짧은 코퍼스·section 문맥을 child 본문 앞에 붙인 임베딩용 입력
- `text`: 검색 결과 인용·리포트 생성에 사용하는 본문

## 5. 문서별 parent 분리 방식

- 산업안전보건법·규칙·고시·개인정보 보호법: 조문 단위
- 별표 11 컨베이어 검사기준: 검사항목 1~33 단위
- 2020 안전검사 매뉴얼: 조작반 외부, 조작반 내부·전기, 이송장치, 종류별 안전장치, 통로·바닥, 검사 주의사항, 전기장비 측정, 물림지점 등 검사 단계 단위
- 2015 컨베이어 교육자료: 컨베이어 종류, 종류별 위험요인·대책, 작업 안전수칙, 재해사례 단위
- 2019 법령해석: 질의요지, 회답, 효력 주의 단위
- 2022 OPS: 중대재해 사례, 통계, 위험요인·안전대책, 안전점검표 단위

## 6. 불필요·중복 구간 처리

`rag_exclusions_dedup.csv`에 모든 제외 근거를 기록했다.

- `11_제조_컨베이어`: 1~2쪽 표지·목차 제외, 17~20쪽 과거 법령·제작기준 복사본 제외
- 2020 컨베이어 매뉴얼:
  - 1~12쪽 표지·목차·업무절차·과거 대상범위 제외
  - 13~14쪽 중복 요약·간지 제외
  - 27쪽 과거 규칙 복사본 제외
  - 35~56쪽 과거 법령·고시 복사본 제외
- 구법 복사 영역은 현행 법·규칙·고시·별표 11과 중복되고 법적 오인 위험이 있어 청킹 전에 제거했다.
- 청킹 이후 추가 완전·근접 중복 child는 발견되지 않았다. `child_dedup_removed_count=0`이다.

## 7. 생성 결과와 QA

- parent: 91개
- child: 358개
- 통합 JSONL 레코드: 449개
- 정확한 20토큰 겹침 검증: 267쌍 PASS
- child 본문 최대: 100토큰
- 임베딩 입력 최대: 123/128토큰
- `[UNK]`: 0개
- parent-child 참조 무결성: PASS
- JSONL 파싱·고유 ID·CSV 행 수: PASS

주의해서 검수할 자료:

- `11_제조_컨베이어_RAG정규화.pdf`: 다단 편집 원문이라 일부 문장 순서 검수 필요
- 2020 매뉴얼: 검사방법 참고용이며 수치·법적 결론은 현행 별표 11과 교차확인
- 2019 법령해석: 2019년 1차 해석이며 현행 기준 없이 단독 인용 금지
- 2022 OPS 통계: 인포그래픽 OCR이므로 통계 수치는 원본 대조 필요

## 8. 주요 산출물

작업 디렉터리:

```text
/workspace/scratch/a9557960c193/output/rag_chunks/
```

파일:

- `conveyor_rag_parent_child_chunks_v1.zip`: 사용자 전달용 전체 묶음
- `rag_parent_child_chunks.jsonl`: parent+child 통합 적재용
- `parent_chunks.jsonl`: parent만 분리
- `child_chunks.jsonl`: 임베딩·FAISS 대상 child만 분리
- `rag_chunk_review.csv`: 사용자 검수용 전체 child 표
- `rag_chunk_review.xlsx`: 필터와 검수 메모가 가능한 통합 검수 문서
- `rag_exclusions_dedup.csv`: 제외·중복 근거
- `rag_build_summary.csv`: 문서별 parent/child 및 토큰 요약
- `chunk_build_config.json`: 설정·QA 결과
- `README_청킹검수.md`: 사용법

생성 스크립트:

```text
/workspace/scratch/a9557960c193/scripts/build_parent_child_chunks.py
/workspace/scratch/a9557960c193/scripts/build_chunk_review_workbook.mjs
/workspace/scratch/a9557960c193/scripts/build_normalized_rag_pdfs.py
```

## 9. JSONL 주요 스키마

Parent 핵심 필드:

```text
record_type, parent_id, corpus, source_filename, doc_type, authority,
retrieval_priority, section, article, item_no, source_pages, hazard_tags,
historical_reference, citation_policy, text_quality, review_note,
parent_text, parent_text_sha256
```

Child 핵심 필드:

```text
record_type, chunk_id, parent_id, corpus, source_filename, section,
source_pages, hazard_tags, historical_reference, citation_policy,
token_count, model_input_token_count, requested_overlap_tokens,
actual_previous_overlap_tokens, embed_text, embed_token_count, text,
text_sha256
```

FAISS에는 `embed_text`를 임베딩하고, 검색 결과 인용·리포트에는 `text`를 사용한다.

## 10. 다음 Codex가 이어서 할 일

권장 순서:

1. `rag_chunk_review.xlsx`에서 `텍스트품질=medium/low`와 `자동검수메모`를 우선 검수
2. 사용자가 `포함여부=N`으로 표시한 청크를 제거하는 확정본 생성 스크립트 작성
3. `child_chunks.jsonl`의 `embed_text`를 `jhgan/ko-sroberta-multitask`로 임베딩
4. 안전 코퍼스와 개인정보 코퍼스를 분리해 FAISS 인덱스 생성
5. `chunk_id ↔ FAISS row`, `parent_id ↔ parent record` 메타데이터 저장
6. 위험 이벤트 메타데이터를 검색 문장으로 만드는 query builder 구현
7. child top-k 검색 후 parent 확장, 코퍼스·검색우선순위·과거자료 여부로 재정렬
8. 검색 근거와 원본 페이지를 포함하는 리포트 생성기 구현
9. KWS 키워드 결과를 `hazard_tags`와 연결
10. 비상정지, 끼임, 불시기동, 역주행·이탈, 추락·낙하, 감전 등 대표 시나리오로 검색 평가

## 11. 구현 시 지켜야 할 사항

- 현재 완료된 정규화·청킹을 이유 없이 처음부터 다시 만들지 않는다.
- 토큰 수를 문자수나 공백 분리로 다시 계산하지 않는다.
- `privacy`를 일반 산업안전 검색 결과에 섞지 않는다.
- `historical_reference=true`를 현행 법적 결론의 최우선 근거로 사용하지 않는다.
- 답변·리포트에는 `source_filename`, `source_pages`, `section`을 근거로 남긴다.
- Vision/KWS가 컨베이어를 실제 정지시키는 제어는 RAG 답변과 분리한다. RAG 지연이나 LLM 실패가 긴급정지를 막아서는 안 된다.
- 이벤트 메타데이터 스키마는 아직 확정하지 말고, 사용자의 임의 값도 받을 수 있도록 어댑터 계층을 둔다.

## 12. 새 Codex에 붙여넣을 시작 메시지

```text
이 프로젝트는 컨베이어 Vision/KWS 위험감지 이벤트를 안전근거 RAG와 연결하는 작업이다.
PDF 정규화와 parent-child 청킹은 완료되어 있으니 다시 청킹하지 말고 CODEX_HANDOFF.md와 output/rag_chunks를 먼저 확인해라.

현재 확정값:
- child 100토큰
- overlap 20토큰
- parent 의미 단위
- embedding model jhgan/ko-sroberta-multitask
- max_seq_length 128
- parent 91개, child 358개

다음 작업은 검수 반영 확정본 생성 → 임베딩 → safety/privacy 분리 FAISS 인덱싱 → 이벤트 query builder → parent 확장 검색 → 근거 포함 리포트 생성 순서다.
이벤트 메타데이터 값은 아직 임의 입력을 허용하고 나중에 통폐합할 수 있게 설계해라.
```
