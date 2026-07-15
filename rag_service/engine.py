from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from .schemas import ActionBasis, EvidenceItem, ReportResponse, RouteName, SearchResponse


PRIVACY_HINTS = {"privacy", "personal", "cctv", "개인정보", "영상정보", "촬영", "녹화", "감시카메라"}
HAZARD_KEYWORDS = {
    "끼임": {"끼임", "협착", "말림", "물림", "nip", "caught"},
    "비상정지": {"비상정지", "정지", "e-stop", "emergency stop", "급정지", "멈춰"},
    "불시기동": {"불시기동", "재기동", "기동", "unexpected start", "오조작"},
    "역주행·이탈": {"역주행", "이탈", "탈선", "벨트 이탈"},
    "추락·낙하": {"추락", "낙하", "떨어짐"},
    "감전": {"감전", "전기", "누전", "접지"},
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def flatten_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        out: list[str] = []
        for nested in value.values():
            out.extend(flatten_values(nested))
        return out
    if isinstance(value, (list, tuple, set)):
        out = []
        for nested in value:
            out.extend(flatten_values(nested))
        return out
    return [str(value)]


def infer_hazard_tags(event: dict[str, Any]) -> list[str]:
    haystack = " ".join(flatten_values(event)).lower()
    tags = []
    for tag, keywords in HAZARD_KEYWORDS.items():
        if any(keyword.lower() in haystack for keyword in keywords):
            tags.append(tag)
    return tags


def choose_route(event: dict[str, Any], explicit: RouteName | None) -> RouteName:
    if explicit:
        return explicit
    haystack = " ".join(flatten_values(event)).lower()
    if any(hint.lower() in haystack for hint in PRIVACY_HINTS):
        return "privacy"
    return "safety"


def build_query(event: dict[str, Any]) -> str:
    hazard_tags = event.get("hazard_tags") or infer_hazard_tags(event)
    parts = []
    for key in (
        "query",
        "description",
        "risk_type",
        "object",
        "equipment",
        "location",
        "observed_action",
    ):
        value = event.get(key)
        if value:
            parts.extend(flatten_values(value))
    for key, label in (("kws_keywords", "KWS 키워드"), ("vision_labels", "Vision 라벨")):
        value = event.get(key)
        if value:
            parts.append(label + ": " + ", ".join(flatten_values(value)))
    if hazard_tags:
        parts.append("위험태그: " + ", ".join(flatten_values(hazard_tags)))
    if not parts:
        parts = flatten_values(event)
    return " | ".join(part for part in parts if part)


def metadata_tags(row: dict[str, Any]) -> set[str]:
    tags = row.get("hazard_tags") or []
    if isinstance(tags, str):
        return {part.strip() for part in re.split(r"[,;/|]", tags) if part.strip()}
    return {str(tag).strip() for tag in tags if str(tag).strip()}


def rerank(row: dict[str, Any], score: float, event_tags: set[str]) -> float:
    adjusted = score
    if row.get("corpus") == "safety_authority":
        adjusted += 0.18
    if row.get("historical_reference"):
        adjusted -= 0.10
    if event_tags and metadata_tags(row) & event_tags:
        adjusted += 0.04
    try:
        adjusted += max(0, 10 - int(row.get("retrieval_priority") or 10)) * 0.005
    except ValueError:
        pass
    return adjusted


def prepare_model_cache() -> None:
    cache_root = Path.cwd() / ".cache" / "huggingface"
    os.environ.setdefault("HF_HOME", str(cache_root.resolve()))
    os.environ.setdefault("HF_HUB_CACHE", str((cache_root / "hub").resolve()))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


class RagEngine:
    def __init__(
        self,
        index_dir: str | Path = "output/rag_indexes",
        model_name: str = "jhgan/ko-sroberta-multitask",
    ) -> None:
        prepare_model_cache()
        import faiss
        from sentence_transformers import SentenceTransformer

        self.faiss = faiss
        self.index_dir = Path(index_dir)
        self.model = SentenceTransformer(model_name)
        self.model.max_seq_length = 128
        self.indexes: dict[str, Any] = {}
        self.metadata: dict[str, list[dict[str, Any]]] = {}
        for route in ("safety", "privacy"):
            group_dir = self.index_dir / route
            self.indexes[route] = faiss.read_index(str(group_dir / "index.faiss"))
            self.metadata[route] = read_jsonl(group_dir / "metadata.jsonl")

    def search(
        self,
        event: dict[str, Any],
        route: RouteName | None = None,
        top_k: int = 5,
        candidate_multiplier: int = 8,
    ) -> SearchResponse:
        selected_route = choose_route(event, route)
        query = build_query(event)
        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype("float32")
        metadata = self.metadata[selected_route]
        candidate_count = min(max(top_k * candidate_multiplier, 30), len(metadata))
        scores, rows = self.indexes[selected_route].search(np.ascontiguousarray(query_embedding), candidate_count)

        event_tags = set(event.get("hazard_tags") or infer_hazard_tags(event))
        by_parent: dict[str, dict[str, Any]] = {}
        for score, row_id in zip(scores[0], rows[0]):
            if row_id < 0:
                continue
            row = metadata[int(row_id)]
            adjusted = rerank(row, float(score), event_tags)
            parent_id = row["parent_id"]
            current = by_parent.get(parent_id)
            if current is None or adjusted > current["adjusted_score"]:
                by_parent[parent_id] = {
                    "score": float(score),
                    "adjusted_score": adjusted,
                    "metadata": row,
                }

        ranked = sorted(by_parent.values(), key=lambda item: item["adjusted_score"], reverse=True)[:top_k]
        results = []
        for rank, item in enumerate(ranked, 1):
            row = item["metadata"]
            results.append(
                EvidenceItem(
                    rank=rank,
                    score=item["score"],
                    adjusted_score=item["adjusted_score"],
                    corpus=row.get("corpus", ""),
                    chunk_id=row.get("chunk_id", ""),
                    parent_id=row.get("parent_id", ""),
                    section=row.get("section"),
                    source_filename=row.get("source_filename"),
                    source_pages=row.get("source_pages"),
                    hazard_tags=row.get("hazard_tags"),
                    historical_reference=bool(row.get("historical_reference")),
                    citation_policy=row.get("citation_policy"),
                    text=row.get("text") or "",
                    parent_text=row.get("parent_text"),
                )
            )
        return SearchResponse(
            event_id=event.get("event_id"),
            route=selected_route,
            query=query,
            inferred_hazard_tags=infer_hazard_tags(event),
            results=results,
        )

    def build_report_basis(
        self,
        event: dict[str, Any],
        route: RouteName | None = None,
        top_k: int = 5,
        candidate_multiplier: int = 8,
        include_markdown: bool = True,
    ) -> ReportResponse:
        search = self.search(event, route=route, top_k=top_k, candidate_multiplier=candidate_multiplier)
        summary = event.get("description") or event.get("risk_type") or "컨베이어 위험 이벤트"
        actions = recommend_actions(search)
        bases = [
            ActionBasis(
                title=item.section or item.chunk_id,
                source=item.source_filename,
                pages=item.source_pages,
                reason=item.citation_policy or "검색된 근거 후보",
                corpus=item.corpus,
                chunk_id=item.chunk_id,
                parent_id=item.parent_id,
            )
            for item in search.results
        ]
        llm_context = {
            "event": event,
            "route": search.route,
            "query": search.query,
            "inferred_hazard_tags": search.inferred_hazard_tags,
            "evidence": [item.model_dump() for item in search.results],
            "guardrails": [
                "RAG 결과는 긴급정지 제어 경로에 사용하지 않는다.",
                "safety_authority를 법적 근거로 우선 사용한다.",
                "historical_reference=true 자료는 단독 법적 결론으로 쓰지 않는다.",
                "privacy 결과는 CCTV/영상정보 문맥에서만 사용한다.",
            ],
        }
        markdown = make_markdown_report(summary, actions, bases, search) if include_markdown else None
        return ReportResponse(
            event_id=event.get("event_id"),
            route=search.route,
            event_summary=summary,
            recommended_action=actions,
            legal_basis=bases,
            llm_context=llm_context,
            markdown=markdown,
        )


def recommend_actions(search: SearchResponse) -> list[str]:
    tags = set(search.inferred_hazard_tags)
    if search.route == "privacy":
        return [
            "CCTV 영상정보의 수집 목적과 보관 범위를 확인한다.",
            "영상 접근 권한과 안전조치 이행 여부를 점검한다.",
            "사고 리포트에는 필요한 최소 범위의 영상정보만 연결한다.",
        ]
    actions = ["컨베이어 운전 정지 상태를 유지하고 현장 접근을 통제한다."]
    if "끼임" in tags:
        actions.append("풀리, 롤러, 체인, 스프라켓 등 물림지점의 덮개·울·물림보호물 설치 상태를 확인한다.")
    if "비상정지" in tags:
        actions.append("작업 위치에서 즉시 조작 가능한 비상정지장치와 풀코드 스위치 작동 상태를 확인한다.")
    if "불시기동" in tags:
        actions.append("점검·보수 중 전원 차단, 시건장치, 작업 중 표지 부착 여부를 확인한다.")
    if "추락·낙하" in tags:
        actions.append("건널다리, 작업발판, 덮개, 울 등 추락·낙하 방지 조치를 확인한다.")
    if len(actions) == 1:
        actions.append("검색 근거의 검사기준을 기준으로 방호장치와 작업절차를 점검한다.")
    return actions


def make_markdown_report(
    summary: str,
    actions: list[str],
    bases: list[ActionBasis],
    search: SearchResponse,
) -> str:
    lines = [
        "# 컨베이어 위험 이벤트 근거 리포트",
        "",
        f"- 이벤트 요약: {summary}",
        f"- 검색 그룹: `{search.route}`",
        f"- 검색 문장: {search.query}",
        "",
        "## 권장 조치",
    ]
    lines.extend(f"- {action}" for action in actions)
    lines.extend(["", "## 근거"])
    for basis, item in zip(bases, search.results):
        historical = " / 과거자료" if item.historical_reference else ""
        lines.extend(
            [
                "",
                f"### {item.rank}. {basis.title}",
                f"- 코퍼스: `{basis.corpus}`{historical}",
                f"- 출처: {basis.source} / p.{basis.pages}",
                f"- ID: `{basis.parent_id}` / `{basis.chunk_id}`",
                f"- 인용 주의: {basis.reason}",
                "",
                item.parent_text or item.text,
            ]
        )
    return "\n".join(lines) + "\n"


@lru_cache(maxsize=1)
def get_engine() -> RagEngine:
    return RagEngine()

