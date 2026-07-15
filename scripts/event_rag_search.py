from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import numpy as np


PRIVACY_HINTS = {"privacy", "personal", "cctv", "개인정보", "영상정보", "촬영", "녹화", "감시카메라"}
HAZARD_KEYWORDS = {
    "끼임": {"끼임", "협착", "말림", "물림", "nip", "caught"},
    "비상정지": {"비상정지", "정지", "e-stop", "emergency stop", "급정지"},
    "불시기동": {"불시기동", "재기동", "기동", "unexpected start"},
    "역주행·이탈": {"역주행", "이탈", "탈선", "벨트 이탈"},
    "추락·낙하": {"추락", "낙하", "떨어짐"},
    "감전": {"감전", "전기", "누전", "접지"},
}


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def require_search_deps():
    cache_root = Path.cwd() / ".cache" / "huggingface"
    os.environ.setdefault("HF_HOME", str(cache_root.resolve()))
    os.environ.setdefault("HF_HUB_CACHE", str((cache_root / "hub").resolve()))
    try:
        import faiss
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing search dependency. Install with: "
            "python -m pip install sentence-transformers faiss-cpu"
        ) from exc
    return faiss, SentenceTransformer


def flatten_values(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        out = []
        for nested in value.values():
            out.extend(flatten_values(nested))
        return out
    if isinstance(value, (list, tuple, set)):
        out = []
        for nested in value:
            out.extend(flatten_values(nested))
        return out
    return [str(value)]


def infer_hazard_tags(event: dict) -> list[str]:
    haystack = " ".join(flatten_values(event)).lower()
    tags = []
    for tag, keywords in HAZARD_KEYWORDS.items():
        if any(keyword.lower() in haystack for keyword in keywords):
            tags.append(tag)
    return tags


def choose_group(event: dict, explicit: str | None) -> str:
    if explicit:
        return explicit
    haystack = " ".join(flatten_values(event)).lower()
    if any(hint.lower() in haystack for hint in PRIVACY_HINTS):
        return "privacy"
    return "safety"


def build_query(event: dict) -> str:
    hazard_tags = event.get("hazard_tags") or infer_hazard_tags(event)
    parts = []
    for key in ("query", "description", "risk_type", "object", "equipment", "location", "observed_action"):
        value = event.get(key)
        if value:
            parts.extend(flatten_values(value))
    kws = event.get("kws_keywords") or event.get("keywords")
    if kws:
        parts.append("KWS 키워드: " + ", ".join(flatten_values(kws)))
    if hazard_tags:
        parts.append("위험태그: " + ", ".join(flatten_values(hazard_tags)))
    if not parts:
        parts = flatten_values(event)
    return " | ".join(part for part in parts if part)


def parse_event(args: argparse.Namespace) -> dict:
    event = {}
    if args.event_json:
        raw = Path(args.event_json).read_text(encoding="utf-8") if Path(args.event_json).exists() else args.event_json
        event.update(json.loads(raw))
    for item in args.set or []:
        if "=" not in item:
            raise SystemExit(f"--set expects key=value, got: {item}")
        key, value = item.split("=", 1)
        if "," in value:
            event[key] = [part.strip() for part in value.split(",") if part.strip()]
        else:
            event[key] = value
    return event


def metadata_tags(row: dict) -> set[str]:
    tags = row.get("hazard_tags") or []
    if isinstance(tags, str):
        return {part.strip() for part in re.split(r"[,;/|]", tags) if part.strip()}
    return {str(tag).strip() for tag in tags if str(tag).strip()}


def rerank(row: dict, score: float, event_tags: set[str]) -> float:
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


def make_report(event: dict, query: str, group: str, results: list[dict]) -> str:
    lines = [
        "# 컨베이어 위험 이벤트 RAG 검색 리포트",
        "",
        f"- 검색 그룹: `{group}`",
        f"- 검색 문장: {query}",
        f"- 추론 위험태그: {', '.join(infer_hazard_tags(event)) or '없음'}",
        "",
        "## 근거 후보",
    ]
    for idx, item in enumerate(results, 1):
        row = item["metadata"]
        historical = " / 과거자료" if row.get("historical_reference") else ""
        lines.extend(
            [
                "",
                f"### {idx}. {row.get('section') or row.get('chunk_id')} ({item['score']:.4f})",
                f"- 코퍼스: `{row.get('corpus')}`{historical}",
                f"- 출처: {row.get('source_filename')} / p.{row.get('source_pages')}",
                f"- parent_id: `{row.get('parent_id')}`, chunk_id: `{row.get('chunk_id')}`",
                f"- 인용 주의: {row.get('citation_policy') or ''}",
                "",
                row.get("parent_text") or row.get("text") or "",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Search conveyor RAG indexes from flexible event metadata.")
    parser.add_argument("--index-dir", default="output/rag_indexes")
    parser.add_argument("--model", default="jhgan/ko-sroberta-multitask")
    parser.add_argument("--event-json", default=None)
    parser.add_argument("--set", action="append", help="Add event metadata as key=value. May be repeated.")
    parser.add_argument("--corpus", choices=["safety", "privacy"], default=None)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-report", default=None)
    args = parser.parse_args()

    faiss, SentenceTransformer = require_search_deps()
    event = parse_event(args)
    query = build_query(event)
    group = choose_group(event, args.corpus)

    group_dir = Path(args.index_dir) / group
    index = faiss.read_index(str(group_dir / "index.faiss"))
    metadata = read_jsonl(group_dir / "metadata.jsonl")

    model = SentenceTransformer(args.model)
    model.max_seq_length = 128
    query_embedding = model.encode([query], convert_to_numpy=True, normalize_embeddings=True).astype("float32")
    candidate_count = min(max(args.top_k * 8, 30), len(metadata))
    scores, rows = index.search(np.ascontiguousarray(query_embedding), candidate_count)

    event_tags = set(event.get("hazard_tags") or infer_hazard_tags(event))
    by_parent = {}
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

    results = sorted(by_parent.values(), key=lambda item: item["adjusted_score"], reverse=True)[: args.top_k]
    payload = {"event": event, "query": query, "group": group, "results": results}

    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = make_report(event, query, group, results)
    if args.output_report:
        Path(args.output_report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_report).write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
