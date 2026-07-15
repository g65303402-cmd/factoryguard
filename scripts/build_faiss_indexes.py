from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np


INDEX_GROUPS = {
    "safety": {"safety_authority", "safety_guidance"},
    "privacy": {"privacy"},
}


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def require_embedding_deps():
    cache_root = Path.cwd() / ".cache" / "huggingface"
    os.environ.setdefault("HF_HOME", str(cache_root.resolve()))
    os.environ.setdefault("HF_HUB_CACHE", str((cache_root / "hub").resolve()))
    try:
        import faiss
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing embedding dependency. Install with: "
            "python -m pip install sentence-transformers faiss-cpu"
        ) from exc
    return faiss, SentenceTransformer


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed reviewed child chunks and build separated FAISS indexes.")
    parser.add_argument("--reviewed-dir", default="output/rag_reviewed")
    parser.add_argument("--output-dir", default="output/rag_indexes")
    parser.add_argument("--model", default="jhgan/ko-sroberta-multitask")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    faiss, SentenceTransformer = require_embedding_deps()

    reviewed_dir = Path(args.reviewed_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    children = read_jsonl(reviewed_dir / "child_chunks.reviewed.jsonl")
    parents = read_jsonl(reviewed_dir / "parent_chunks.reviewed.jsonl")
    parent_map = {parent["parent_id"]: parent for parent in parents}

    model = SentenceTransformer(args.model)
    model.max_seq_length = 128

    manifest = {
        "embedding_model": args.model,
        "embedding_model_max_seq_length": 128,
        "distance": "inner_product_on_l2_normalized_embeddings",
        "groups": {},
    }

    for group_name, corpora in INDEX_GROUPS.items():
        group_children = [child for child in children if child.get("corpus") in corpora]
        group_dir = output_dir / group_name
        group_dir.mkdir(parents=True, exist_ok=True)

        if not group_children:
            manifest["groups"][group_name] = {"child_count": 0, "corpora": sorted(corpora)}
            continue

        texts = [child["embed_text"] for child in group_children]
        embeddings = model.encode(
            texts,
            batch_size=args.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=True,
        ).astype("float32")

        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(np.ascontiguousarray(embeddings))
        faiss.write_index(index, str(group_dir / "index.faiss"))

        metadata = []
        for row_id, child in enumerate(group_children):
            parent = parent_map[child["parent_id"]]
            metadata.append(
                {
                    "faiss_row": row_id,
                    "chunk_id": child["chunk_id"],
                    "parent_id": child["parent_id"],
                    "corpus": child["corpus"],
                    "source_filename": child.get("source_filename"),
                    "source_pages": child.get("source_pages"),
                    "section": child.get("section"),
                    "hazard_tags": child.get("hazard_tags", []),
                    "historical_reference": child.get("historical_reference", False),
                    "retrieval_priority": child.get("retrieval_priority"),
                    "citation_policy": child.get("citation_policy"),
                    "text": child.get("text"),
                    "parent_text": parent.get("parent_text"),
                    "parent_record": parent,
                }
            )
        write_jsonl(group_dir / "metadata.jsonl", metadata)

        manifest["groups"][group_name] = {
            "corpora": sorted(corpora),
            "child_count": len(group_children),
            "embedding_dimension": int(embeddings.shape[1]),
            "index_path": str(group_dir / "index.faiss"),
            "metadata_path": str(group_dir / "metadata.jsonl"),
        }

    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
