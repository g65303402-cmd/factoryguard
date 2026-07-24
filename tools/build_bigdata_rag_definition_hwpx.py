from __future__ import annotations

import copy
import io
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "빅데이터분석정의서.hwpx"
OUTPUT = ROOT / "빅데이터분석정의서_RAG반영.hwpx"

SUBJECT = "컨베이어 안전 RAG 지식베이스 구축 및 근거 리포트 분석"
DATE_TEXT = "2026. 07. 22."
FUNCTION_NAME = (
    "컨베이어 위험 이벤트 RAG 검색 및 근거 리포트 생성 "
    "(FR-DM-001~002, FR-AI-001~006, FR-RP-001~002, FR-API-001)"
)

DETAILS = {
    2: (
        "산업안전 법령·고시·검사기준·안전매뉴얼·법령해석과 CCTV 개인정보 법령의 본문 및 메타데이터, "
        "그리고 Vision/KWS/Backend가 생성하는 위험 이벤트 데이터를 사용한다. 문서 메타데이터는 source_filename, "
        "source_pages, doc_type, authority, corpus, section, hazard_tags, historical_reference, retrieval_priority, "
        "citation_policy로 정의한다. 이벤트는 description, risk_type, object/equipment, location, observed_action, "
        "kws_keywords, vision_labels를 포함한다."
    ),
    3: (
        "공식 기관에서 원문 PDF를 수집한 뒤 프로젝트 폴더에 보관했다. 확보량은 정규화 대상 10종이다. "
        "주요 출처: 국가법령정보센터 산업안전보건법 "
        "https://www.law.go.kr/LSW/lsInfoP.do?ancNo=21374&ancYd=20260219&efYd=20260601&lsiSeq=283449, "
        "국가법령정보센터 통합검색 https://www.law.go.kr, 고용노동부 훈령·예규·고시 "
        "https://www.moel.go.kr/info/lawinfo/instruction/list.do, 한국산업안전보건공단 "
        "https://www.kosha.or.kr, 유해·위험기계·기구 종합정보시스템 https://miis.kosha.or.kr. "
        "수집본은 ‘원본 문서확보’, RAG용 문서는 ‘컨베이어_RAG_정규화_PDF_묶음’에서 관리한다."
    ),
    4: (
        "수집 문서 10종: 산업안전보건법, 산업안전보건기준에 관한 규칙, 안전검사 고시, [별표 11] 컨베이어 검사기준, "
        "안전검사 절차에 관한 고시, 개인정보 보호법(CCTV 별도), 고용노동부 법령해석, 컨베이어 안전검사 매뉴얼, "
        "컨베이어 기술지침, 제조업 컨베이어 안전자료. 예시 레코드: corpus=safety_authority, "
        "section=‘검사항목 5. 덮개 또는 울’, source_pages=[2,3], hazard_tags=[끼임, 비상정지]."
    ),
    6: (
        "1) PDF에서 반복 머리말·꼬리말, 깨진 줄바꿈, 불필요 표식과 검색 방해 구간을 정리해 RAG 정규화 PDF를 생성한다. "
        "2) 현행 법령은 safety_authority, 안내·매뉴얼은 safety_guidance, CCTV 법령은 privacy로 분류한다. "
        "3) 조문·검사항목·위험요인 단위로 parent를 구성한다. 4) BertTokenizer WordPiece 기준 child 본문 최대 100토큰, "
        "연속 중첩 20토큰, 특수토큰 포함 임베딩 입력 최대 128토큰으로 분할한다. 5) 원문 페이지·문서명·인용정책을 상속한다. "
        "6) 검수표의 포함/제외 결정을 적용하고 참조 무결성·토큰 제한·중첩·중복을 자동 검사한다."
    ),
    7: (
        "전처리 결과 parent 91건, child 358건이다. 358개 검수 행이 모두 승인되어 reviewed corpus에 반영되었고, "
        "제외·중복 근거 기록은 8건, 실제 child 중복 제거는 0건이다. 연속 청크 267쌍의 20토큰 중첩을 검증했으며 "
        "미등록 토큰은 0건이다. 최종 child는 안전 329건(safety_authority/safety_guidance)과 개인정보 29건(privacy)으로 분리됐다."
    ),
    9: (
        "위험 이벤트의 의미와 가장 관련성이 높은 현행 법령·검사기준·안전지침을 검색하고, CCTV 문맥은 개인정보 근거만 "
        "조회하도록 분리한다. 검색 결과가 원본 문서와 페이지까지 추적되도록 하며 현행 법령 우선, 과거자료 단독 법적 결론 금지, "
        "위험태그 일치 우대 규칙을 적용해 사후 리포트의 근거 품질을 높인다."
    ),
    10: (
        "1) 이벤트의 설명·위험유형·설비·위치·관찰행동·KWS 키워드·Vision 라벨을 결합해 검색문을 만든다. "
        "2) 끼임·비상정지·불시기동 등 위험태그를 추론한다. 3) CCTV·촬영·영상정보·개인정보 단어가 있으면 privacy, "
        "그 외에는 safety 인덱스로 라우팅한다. 4) jhgan/ko-sroberta-multitask로 질의를 768차원 벡터화하고 L2 정규화한다. "
        "5) FAISS IndexFlatIP에서 top_k×candidate_multiplier 후보(최소 30건)를 검색한다. 6) parent_id 기준 중복을 제거한다. "
        "7) safety_authority +0.18, historical_reference -0.10, 위험태그 일치 +0.04, 검색우선순위 가점을 적용해 재정렬한다. "
        "8) 출처·페이지·parent/child ID와 함께 상위 근거를 반환한다."
    ),
    11: (
        "안전 이벤트 예시(‘컨베이어 풀리 물림점에 작업자 손 끼임 위험’)의 1위는 [별표 11] 컨베이어 검사기준의 "
        "‘검사항목 5. 덮개 또는 울’로 검색되었다(score 0.8135, adjusted 1.0785). 개인정보 예시(CCTV 녹화자료 사용 검토)의 "
        "1위는 개인정보 보호법 제25조로 검색되었다(score 0.7129, adjusted 0.7579). 두 예시 모두 의도한 안전/개인정보 경로와 "
        "출처 페이지, 인용정책을 반환했다."
    ),
    13: (
        "위험 이벤트 문장과 법령·지침 child 청크 사이의 의미 유사도를 계산해 관련 근거 후보를 순위화한다. "
        "별도 위험 판정 모델을 새로 학습하는 것이 아니라, 사전학습 한국어 문장 임베딩 모델을 검색 표현 모델로 사용한다."
    ),
    14: (
        "임베딩 모델: jhgan/ko-sroberta-multitask(SentenceTransformer, 최대 입력 128토큰, 출력 768차원). "
        "검색 모델: FAISS IndexFlatIP. 토크나이저: BertTokenizer, WordPiece 32,000 vocabulary."
    ),
    15: (
        "추가 지도학습이나 파인튜닝은 수행하지 않는다. 검수 완료 child의 embed_text를 batch size 32로 인코딩하고 "
        "normalize_embeddings=True로 L2 정규화한 float32 벡터를 생성한다. 안전 329건과 개인정보 29건을 각각 별도 "
        "IndexFlatIP에 등록하며, 동일 순서의 metadata.jsonl에 원문·페이지·청크·코퍼스 정보를 저장한다."
    ),
    16: (
        "모델 산출물은 safety/index.faiss(329벡터)와 privacy/index.faiss(29벡터)이며 각 벡터 차원은 768이다. "
        "안전 예시 질의에서는 물림보호물·덮개 근거, 개인정보 예시 질의에서는 영상정보처리기기 설치·운영 제한과 안전조치의무가 "
        "상위 결과로 예측됐다."
    ),
    18: (
        "① 구조 검증: parent-child 참조 무결성, 청크 ID 유일성, 토큰 상한, 20토큰 중첩, 미등록 토큰, 인덱스-메타데이터 건수를 검사한다. "
        "② 내용 검증: 원본 파일명·페이지와 정규화 PDF를 대조하고 저품질/OCR 청크를 검수한다. ③ 검색 검증: 안전·개인정보 대표 이벤트로 "
        "라우팅, top-k 관련성, parent 중복 제거, 현행 법령 가점, 과거자료 감점, 인용정책을 확인한다. ④ API 회귀검증: /health, /rag/search, "
        "/rag/report 응답 스키마와 장애 시 긴급정지 경로 분리를 확인한다."
    ),
    19: (
        "자동 QA 결과 referential_integrity=PASS, token_limit_check=PASS, overlap_check=PASS, unknown_token_count=0이다. "
        "reviewed corpus는 parent 91건·child 358건, 최종 인덱스는 safety 329건·privacy 29건으로 manifest와 일치한다. "
        "안전/개인정보 대표 검색 2건의 스모크 테스트는 의도한 경로와 근거를 반환했다. 다만 Precision@K·Recall@K 등 정량 검색품질은 "
        "별도 라벨링 평가셋이 없어 미산출 상태이며, 후속 검수셋 구축 후 측정한다."
    ),
}

ROW_HEIGHTS = {
    0: 3300,
    2: 7200,
    3: 9800,
    4: 7500,
    6: 10500,
    7: 7200,
    9: 6600,
    10: 12500,
    11: 7000,
    13: 5200,
    14: 5200,
    15: 6800,
    16: 6000,
    18: 10000,
    19: 8500,
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def text_nodes(element: ET.Element) -> list[ET.Element]:
    return [node for node in element.iter() if local_name(node.tag) == "t"]


def clear_line_segments(element: ET.Element) -> None:
    for paragraph in [node for node in element.iter() if local_name(node.tag) == "p"]:
        for child in list(paragraph):
            if local_name(child.tag) == "linesegarray":
                paragraph.remove(child)


def set_element_text(element: ET.Element, value: str) -> None:
    nodes = text_nodes(element)
    if not nodes:
        run = next((node for node in element.iter() if local_name(node.tag) == "run"), None)
        if run is None:
            raise RuntimeError("텍스트를 삽입할 run 요소가 없습니다.")
        namespace = run.tag.split("}", 1)[0].lstrip("{")
        nodes = [ET.SubElement(run, f"{{{namespace}}}t")]
    nodes[0].text = value
    for node in nodes[1:]:
        node.text = ""
    clear_line_segments(element)


def table_rows(table: ET.Element) -> list[list[ET.Element]]:
    rows: list[list[ET.Element]] = []
    for row in table:
        if local_name(row.tag) == "tr":
            rows.append([cell for cell in row if local_name(cell.tag) == "tc"])
    return rows


def replace_exact(root: ET.Element, old: str, new: str) -> None:
    matches = [node for node in root.iter() if local_name(node.tag) == "t" and (node.text or "") == old]
    if not matches:
        raise RuntimeError(f"치환할 텍스트를 찾지 못했습니다: {old}")
    for node in matches:
        node.text = new


def set_row_height(cells: list[ET.Element], height: int) -> None:
    for cell in cells:
        size = next((node for node in cell if local_name(node.tag) == "cellSz"), None)
        if size is not None:
            size.set("height", str(height))


def update_section(section_bytes: bytes) -> bytes:
    namespaces: dict[str, str] = {}
    for _, item in ET.iterparse(io.BytesIO(section_bytes), events=("start-ns",)):
        prefix, uri = item
        if prefix not in namespaces:
            namespaces[prefix] = uri
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)

    root = ET.fromstring(section_bytes)
    tables = [node for node in root.iter() if local_name(node.tag) == "tbl"]
    if len(tables) != 5:
        raise RuntimeError(f"예상한 표 5개가 아닌 {len(tables)}개입니다.")

    set_element_text(table_rows(tables[2])[0][1], SUBJECT)
    replace_exact(root, "발표회 날짜로 작성", "")
    set_element_text(table_rows(tables[3])[0][0], DATE_TEXT)

    replace_exact(
        root,
        " 1) 아이디어 주제 ",
        " 1) 아이디어 주제 : 다중 AI 감지 이벤트 기반 컨베이어 안전 법령·지침 RAG 검색 및 사후 근거 리포트 생성",
    )
    replace_exact(
        root,
        "- ",
        "- 정규화·검수된 공식 문서에서 위험 이벤트와 관련된 근거를 신속히 검색하고, 출처·원문 페이지·권장조치가 포함된 리포트용 컨텍스트를 생성한다.",
    )
    replace_exact(
        root,
        " 3) 개발 내용",
        " 3) 개발 내용 : 공식 문서 10종 정규화, parent-child 청킹 및 검수, 안전/개인정보 코퍼스 분리, 한국어 임베딩·FAISS 인덱싱, 이벤트 라우팅·재정렬, 근거 리포트 API 및 검증",
    )

    rows = table_rows(tables[4])
    if len(rows) != 20:
        raise RuntimeError("분석 명세 표의 행 수가 20개가 아닙니다.")
    set_element_text(rows[0][1], FUNCTION_NAME)
    set_element_text(rows[1][0], "1. 데이터 준비")
    for row_index, value in DETAILS.items():
        set_element_text(rows[row_index][1], value)
    for row_index, height in ROW_HEIGHTS.items():
        set_row_height(rows[row_index], height)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_preview_text() -> str:
    lines = [
        "<빅데이터 분석 정의서>",
        f"<주제 :> {SUBJECT}",
        f"<{DATE_TEXT}>",
        "",
        "1. 개요",
        "1) 아이디어 주제: 다중 AI 감지 이벤트 기반 컨베이어 안전 법령·지침 RAG 검색 및 사후 근거 리포트 생성",
        "2) 개발 목표: 정규화·검수된 공식 문서에서 위험 이벤트와 관련된 근거를 검색하고 출처·페이지가 포함된 리포트 컨텍스트를 생성한다.",
        "3) 개발 내용: 공식 문서 10종 정규화, parent-child 청킹 및 검수, 안전/개인정보 분리, 임베딩·FAISS 인덱싱, 이벤트 라우팅·재정렬, API 및 검증",
        "",
        "2. 기능별 빅데이터 분석 명세서",
        f"기능명: {FUNCTION_NAME}",
    ]
    labels = {
        2: "데이터 정의",
        3: "데이터 획득 방법",
        4: "수집 데이터",
        6: "전처리 과정",
        7: "전처리 데이터",
        9: "데이터 분석 목표",
        10: "데이터 분석 시나리오",
        11: "데이터 분석 결과",
        13: "모델링 목표",
        14: "학습 모델",
        15: "학습 방법",
        16: "모델 예측 결과",
        18: "분석 검증 방안",
        19: "분석 평가 결과",
    }
    for index in sorted(DETAILS):
        lines.append(f"{labels[index]}: {DETAILS[index]}")
    return "\n".join(lines) + "\n"


def main() -> None:
    with zipfile.ZipFile(SOURCE, "r") as source_zip:
        section = update_section(source_zip.read("Contents/section0.xml"))
        with zipfile.ZipFile(OUTPUT, "w") as output_zip:
            output_zip.writestr("mimetype", source_zip.read("mimetype"), compress_type=zipfile.ZIP_STORED)
            for info in source_zip.infolist():
                if info.filename == "mimetype":
                    continue
                data = source_zip.read(info.filename)
                if info.filename == "Contents/section0.xml":
                    data = section
                elif info.filename == "Preview/PrvText.txt":
                    data = build_preview_text().encode("utf-8")
                output_zip.writestr(copy.copy(info), data)

    with zipfile.ZipFile(OUTPUT, "r") as check_zip:
        if check_zip.namelist()[0] != "mimetype":
            raise RuntimeError("mimetype이 첫 항목이 아닙니다.")
        if check_zip.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
            raise RuntimeError("mimetype이 무압축이 아닙니다.")
        if check_zip.testzip() is not None:
            raise RuntimeError("ZIP CRC 검증에 실패했습니다.")
        for name in check_zip.namelist():
            if name.endswith((".xml", ".hpf", ".rdf")):
                ET.fromstring(check_zip.read(name))
    print(OUTPUT)


if __name__ == "__main__":
    main()
