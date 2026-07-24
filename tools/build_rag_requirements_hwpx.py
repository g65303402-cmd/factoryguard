from __future__ import annotations

import copy
import io
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "요구사항정의서.hwpx"
OUTPUT = ROOT / "요구사항정의서_RAG반영.hwpx"


PROJECT_NAME = "공장수호대 - 다중 AI 감지 기반 컨베이어 사고 자동 정지 및 사후 분석 서비스"
DATE_TEXT = "2026. 07. 22."


FUNCTIONAL_REQUIREMENTS = [
    (
        "FR-DM-001",
        "RAG 원천문서 등록",
        "컨베이어 안전·검사·법령·개인정보 관련 정규화 PDF 10종을 등록하고, 원본 파일명·문서 구분·원문 페이지·인용 주의사항 메타데이터를 함께 관리한다.",
        "상",
    ),
    (
        "FR-DM-002",
        "코퍼스 분류 및 격리",
        "문서를 safety_authority, safety_guidance, privacy로 분류하고 CCTV·영상정보 질의는 privacy 인덱스에서만 검색되도록 안전 문서와 물리적으로 분리한다.",
        "상",
    ),
    (
        "FR-AI-001",
        "Parent-Child 청킹",
        "검수된 91개 parent와 358개 child를 사용한다. child 본문은 최대 100 WordPiece, 연속 청크 중첩은 20토큰, 임베딩 입력은 특수토큰 포함 최대 128토큰으로 구성한다.",
        "상",
    ),
    (
        "FR-AI-002",
        "청크 검수 결과 반영",
        "358개 검수 행의 포함·제외 결정을 적용해 reviewed corpus를 생성하고, 현재 승인된 parent 91건과 child 358건이 누락 없이 인덱싱 대상에 포함되도록 한다.",
        "중",
    ),
    (
        "FR-AI-003",
        "임베딩 및 FAISS 인덱스",
        "jhgan/ko-sroberta-multitask로 L2 정규화된 768차원 임베딩을 생성한다. 안전 329건과 개인정보 29건을 별도 FAISS inner-product 인덱스로 구축한다.",
        "상",
    ),
    (
        "FR-AI-004",
        "이벤트 검색문 생성",
        "Vision·KWS·Backend·수동 이벤트의 설명, 위험유형, 설비, 위치, 관찰행동, KWS 키워드, Vision 라벨을 조합하고 끼임·비상정지·불시기동 등 위험 태그를 추론한다.",
        "상",
    ),
    (
        "FR-AI-005",
        "검색 경로 자동 선택",
        "CCTV·촬영·영상정보·개인정보 문맥은 privacy 경로로, 그 외 컨베이어 안전 이벤트는 safety 경로로 자동 라우팅하며 요청자가 경로를 명시할 수도 있어야 한다.",
        "상",
    ),
    (
        "FR-AI-006",
        "근거 검색 및 재정렬",
        "top_k 1~20 범위에서 후보를 검색하고 parent 단위로 중복 제거한다. 현행 법령(safety_authority), 위험태그 일치, 검색 우선순위를 가점하고 historical_reference 자료는 감점한다.",
        "상",
    ),
    (
        "FR-RP-001",
        "검색 근거 추적",
        "각 결과에 순위, 원점수·조정점수, 코퍼스, chunk_id, parent_id, 조·절, 원본 파일명, 원문 페이지, 과거자료 여부, 인용정책 및 본문을 반환한다.",
        "상",
    ),
    (
        "FR-RP-002",
        "근거 기반 리포트 생성",
        "이벤트 요약, 권장조치, 법적 근거, LLM 컨텍스트와 Markdown 초안을 생성한다. 현행 법령을 우선하고 과거자료를 단독 법적 결론으로 사용하지 않는 가드레일을 포함한다.",
        "상",
    ),
    (
        "FR-API-001",
        "RAG API 및 화면 연계",
        "GET /health, POST /rag/search, POST /rag/report를 제공하고 관리자 대시보드가 검색 근거와 리포트를 조회할 수 있게 한다. RAG 장애가 긴급 자동정지 경로를 차단해서는 안 된다.",
        "상",
    ),
]


NONFUNCTIONAL_REQUIREMENTS = [
    (
        "NFR-AN-001",
        "데이터 추적성·재현성",
        "인덱스 manifest에 모델명, 최대 입력 길이, 거리 방식, 코퍼스별 건수·차원·파일 경로를 기록하고 원문 페이지와 청크 ID로 모든 검색 결과를 역추적할 수 있어야 한다.",
        "분석/개발",
    ),
    (
        "NFR-DV-001",
        "성능 및 장애 격리",
        "모델과 인덱스가 예열된 상태에서 일반 top_k=5 검색·리포트 근거 생성 API는 5초 이내 응답을 목표로 하며, RAG 오류 시에도 Vision/KWS 기반 긴급정지는 독립 동작해야 한다.",
        "개발/테스트",
    ),
    (
        "NFR-DV-002",
        "개인정보 최소처리",
        "CCTV 관련 질의와 근거는 privacy 코퍼스로 분리하고, 리포트에는 목적 달성에 필요한 최소한의 영상정보만 연결한다. 접근권한과 조회 이력을 관리할 수 있어야 한다.",
        "설계/개발",
    ),
    (
        "NFR-TS-001",
        "검색 품질·안전성 검증",
        "안전·개인정보 대표 이벤트로 회귀시험을 수행한다. 결과마다 출처·페이지·parent/child ID가 존재하고, 현행 법령 우선·과거자료 단독결론 금지·privacy 분리 규칙을 모두 만족해야 한다.",
        "테스트",
    ),
]


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def text_nodes(element: ET.Element) -> list[ET.Element]:
    return [node for node in element.iter() if local_name(node.tag) == "t"]


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


def table_rows(table: ET.Element) -> list[list[ET.Element]]:
    rows: list[list[ET.Element]] = []
    for row in table:
        if local_name(row.tag) != "tr":
            continue
        rows.append([cell for cell in row if local_name(cell.tag) == "tc"])
    return rows


def replace_exact(root: ET.Element, old: str, new: str) -> None:
    matches = [node for node in root.iter() if local_name(node.tag) == "t" and (node.text or "") == old]
    if not matches:
        raise RuntimeError(f"치환할 텍스트를 찾지 못했습니다: {old}")
    for node in matches:
        node.text = new


def update_section(section_bytes: bytes) -> bytes:
    # 원본의 namespace prefix를 보존한다.
    namespaces: dict[str, str] = {}
    for _, item in ET.iterparse(io.BytesIO(section_bytes), events=("start-ns",)):
        prefix, uri = item
        if prefix not in namespaces:
            namespaces[prefix] = uri
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)

    root = ET.fromstring(section_bytes)
    tables = [node for node in root.iter() if local_name(node.tag) == "tbl"]
    if len(tables) != 7:
        raise RuntimeError(f"예상한 표 7개가 아닌 {len(tables)}개입니다.")

    # 표지 및 개요
    set_element_text(table_rows(tables[1])[0][1], PROJECT_NAME)
    replace_exact(root, "발표회 날짜로 작성", "")
    set_element_text(table_rows(tables[2])[0][0], DATE_TEXT)
    replace_exact(root, "프로젝트에 맞게 수정", "")
    replace_exact(root, "“OpenAI 활용 초개인화 식단 추천 서비스”", f"“{PROJECT_NAME}”")
    replace_exact(
        root,
        "상기 서비스는 식품의약품안전처 공공데이터 API를 활용하여 검증된 영양 정보를 제공하며 OpenAI를 활용해 사용자의 신체 데이터, 기저질환, 알레르기를 반영한 맞춤형 식단 생성을 목표로 한다.",
        "상기 서비스는 Vision AI와 다국어 KWS가 생성한 컨베이어 위험 이벤트를 수신하고, 확보·정규화·검수한 산업안전 법령 및 지침 데이터에서 근거를 검색하여 출처와 원문 페이지가 포함된 사후 분석 리포트를 생성하는 것을 목표로 한다.",
    )
    replace_exact(root, "초개인화 식단 생성 웹서비스 개발", "컨베이어 안전 감지·RAG 사후 분석 서비스 개발")
    replace_exact(
        root,
        "본 문서에서는 유스케이스 및 기능·비기능 요구사항의 기술을 그 범위로 한다.",
        "본 문서에서는 위험 이벤트 수신부터 문서 라우팅, 의미 검색, 근거 재정렬, 출처 추적, 사후 리포트 생성 및 관리자 화면 연계까지의 유스케이스와 기능·비기능 요구사항을 범위로 한다. 컨베이어 긴급정지 제어 자체는 RAG 처리와 분리한다.",
    )
    replace_exact(root, "유스케이스 별 상세 명세 작성", "")

    # 유스케이스 다이어그램(텍스트 흐름도)
    diagram = (
        "[작업자·컨베이어] → [Vision AI / 다국어 KWS] → [Backend 위험 이벤트] → "
        "[RAG 검색 API] → [안전 FAISS 329건 / 개인정보 FAISS 29건] → "
        "[출처·페이지 포함 근거 리포트] → [안전관리자 대시보드]"
    )
    set_element_text(table_rows(tables[5])[0][0], diagram)

    # 유스케이스 명세
    use_case = table_rows(tables[3])
    labels = [
        "유스케이스 이름",
        "유스케이스 ID",
        "관련 요구사항",
        "우선순위",
        "선행조건",
        "관련 액터",
        "이벤트 흐름",
        "종료조건",
    ]
    values = [
        "위험 이벤트 기반 RAG 근거 리포트 생성",
        "FG_RAG_100",
        "FR-AI-004~006, FR-RP-001~002, FR-API-001",
        "상",
        "정규화·검수된 358개 child가 안전/개인정보 FAISS 인덱스로 구축되고 RAG API가 정상 기동되어 있다.",
        "Vision AI·KWS·Backend, 안전관리자, 리포트 생성 LLM",
        "1) 감지 시스템이 위험 이벤트를 전송한다. 2) API가 검색문과 위험태그를 생성한다. 3) 안전/개인정보 경로를 선택한다. 4) 후보 청크를 검색하고 parent 중복을 제거한다. 5) 현행 법령과 태그 일치도를 반영해 재정렬한다. 6) 출처·페이지·청크 ID를 포함한 근거를 반환한다. 7) 권장조치와 리포트 초안을 생성해 대시보드에 제공한다.",
        "관리자가 근거와 인용 주의사항을 확인할 수 있는 리포트가 생성·조회되며, RAG 성공 여부와 관계없이 긴급 자동정지 제어는 독립적으로 완료된다.",
    ]
    for row, label, value in zip(use_case, labels, values):
        set_element_text(row[0], label)
        set_element_text(row[1], value)

    # 기능 요구사항
    functional = table_rows(tables[4])
    headers = ["ID", "요구사항명칭", "설명", "우선순위"]
    for cell, header in zip(functional[0], headers):
        set_element_text(cell, header)
    if len(functional) - 1 != len(FUNCTIONAL_REQUIREMENTS):
        raise RuntimeError("기능 요구사항 행 수가 템플릿과 일치하지 않습니다.")
    for row, requirement in zip(functional[1:], FUNCTIONAL_REQUIREMENTS):
        for cell, value in zip(row, requirement):
            set_element_text(cell, value)

    # 비기능 요구사항
    nonfunctional = table_rows(tables[6])
    headers = ["ID", "요구사항명칭", "설명", "적용시점"]
    for cell, header in zip(nonfunctional[0], headers):
        set_element_text(cell, header)
    if len(nonfunctional) - 1 != len(NONFUNCTIONAL_REQUIREMENTS):
        raise RuntimeError("비기능 요구사항 행 수가 템플릿과 일치하지 않습니다.")
    for row, requirement in zip(nonfunctional[1:], NONFUNCTIONAL_REQUIREMENTS):
        for cell, value in zip(row, requirement):
            set_element_text(cell, value)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_preview_text() -> str:
    lines = [
        "<요구사항 정의서>",
        f"<과제명 :> {PROJECT_NAME}",
        f"<{DATE_TEXT}>",
        "",
        "개요",
        "□ 문서의 목적",
        f"본 문서는 “{PROJECT_NAME}” 개발의 요구사항을 정의한 문서이다.",
        "Vision AI와 다국어 KWS가 생성한 컨베이어 위험 이벤트를 수신하고, 확보·정규화·검수한 산업안전 법령 및 지침 데이터에서 근거를 검색하여 출처와 원문 페이지가 포함된 사후 분석 리포트를 생성한다.",
        "",
        "□ 요구사항 및 문서의 범위",
        "위험 이벤트 수신, 문서 라우팅, 의미 검색, 근거 재정렬, 출처 추적, 사후 리포트 생성 및 관리자 화면 연계를 범위로 한다. 긴급정지 제어 자체는 RAG 처리와 분리한다.",
        "",
        "유스케이스",
        "위험 이벤트 기반 RAG 근거 리포트 생성 (FG_RAG_100)",
        "",
        "기능 요구사항",
    ]
    lines.extend(" | ".join(row) for row in FUNCTIONAL_REQUIREMENTS)
    lines.extend(["", "비기능 요구사항"])
    lines.extend(" | ".join(row) for row in NONFUNCTIONAL_REQUIREMENTS)
    return "\n".join(lines) + "\n"


def main() -> None:
    with zipfile.ZipFile(SOURCE, "r") as source_zip:
        section = update_section(source_zip.read("Contents/section0.xml"))
        with zipfile.ZipFile(OUTPUT, "w") as output_zip:
            # HWPX 호환성을 위해 mimetype을 첫 항목·무압축으로 기록한다.
            mime_info = source_zip.getinfo("mimetype")
            output_zip.writestr("mimetype", source_zip.read("mimetype"), compress_type=zipfile.ZIP_STORED)
            for info in source_zip.infolist():
                if info.filename == "mimetype":
                    continue
                data = source_zip.read(info.filename)
                if info.filename == "Contents/section0.xml":
                    data = section
                elif info.filename == "Preview/PrvText.txt":
                    data = build_preview_text().encode("utf-8")
                new_info = copy.copy(info)
                output_zip.writestr(new_info, data)

    # 구조 검증
    with zipfile.ZipFile(OUTPUT, "r") as check_zip:
        if check_zip.namelist()[0] != "mimetype":
            raise RuntimeError("mimetype이 첫 항목이 아닙니다.")
        if check_zip.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
            raise RuntimeError("mimetype이 무압축이 아닙니다.")
        for name in check_zip.namelist():
            if name.endswith((".xml", ".hpf", ".rdf")):
                ET.fromstring(check_zip.read(name))
    print(OUTPUT)


if __name__ == "__main__":
    main()
