"""
workers/retrieval.py — Retrieval Worker
Sprint 2: Implement retrieval từ ChromaDB, trả về chunks + sources.

Input (từ AgentState):
    - task: câu hỏi cần retrieve
    - (optional) retrieved_chunks nếu đã có từ trước

Output (vào AgentState):
    - retrieved_chunks: list of {"text", "source", "score", "metadata"}
    - retrieved_sources: list of source filenames
    - worker_io_log: log input/output của worker này

Gọi độc lập để test:
    python workers/retrieval.py
"""

import os
import re
import sys
from pathlib import Path

# ─────────────────────────────────────────────
# Worker Contract (xem contracts/worker_contracts.yaml)
# Input:  {"task": str, "top_k": int = 3}
# Output: {"retrieved_chunks": list, "retrieved_sources": list, "error": dict | None}
# ─────────────────────────────────────────────

WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = 3
EMBEDDING_MODEL = "text-embedding-3-small"
MIN_SCORE = 0.48

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

def _get_embedding_fn():
    """
    Trả về embedding function.
    ChromaDB Day09 đã được build bằng OpenAI `text-embedding-3-small`, nên
    query embedding cũng phải dùng đúng model này.
    """
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY chưa được thiết lập trong .env")

    client = OpenAI(api_key=api_key)

    def embed(text: str) -> list:
        resp = client.embeddings.create(input=text, model=EMBEDDING_MODEL)
        return resp.data[0].embedding

    return embed


def _get_collection():
    """
    Kết nối ChromaDB collection.
    TODO Sprint 2: Đảm bảo collection đã được build từ Step 3 trong README.
    """
    import chromadb
    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        collection = client.get_collection("day09_docs")
    except Exception:
        # Auto-create nếu chưa có
        collection = client.get_or_create_collection(
            "day09_docs",
            metadata={"hnsw:space": "cosine"}
        )
        print(f"⚠️  Collection 'day09_docs' chưa có data. Chạy index script trong README trước.")
    return collection


def _clamp_score(score: float) -> float:
    return round(max(0.0, min(1.0, score)), 4)


def _format_chroma_results(results: dict) -> list[dict]:
    documents = (results.get("documents") or [[]])[0] or []
    metadatas = (results.get("metadatas") or [[]])[0] or [{} for _ in documents]
    distances = (results.get("distances") or [[]])[0] or [None for _ in documents]

    chunks = []
    for doc, dist, meta in zip(documents, distances, metadatas):
        metadata = meta or {}
        source = (
            metadata.get("source")
            or metadata.get("filename")
            or metadata.get("file")
            or metadata.get("path")
            or "unknown"
        )
        source = Path(str(source)).name
        score = 0.5 if dist is None else 1.0 - float(dist)
        chunks.append({
            "text": doc,
            "source": source,
            "score": _clamp_score(score),
            "metadata": metadata,
        })
    return chunks


def _filter_unknown_error_code(query: str, chunks: list) -> list:
    """
    Vector search luôn trả nearest chunks. Với mã lỗi cụ thể, nếu exact code
    không xuất hiện trong evidence thì trả rỗng để synthesis abstain.
    """
    error_codes = re.findall(r"\bERR-[A-Z0-9-]+\b", query.upper())
    if not error_codes:
        return chunks

    evidence = "\n".join(c.get("text", "") for c in chunks).upper()
    if any(code in evidence for code in error_codes):
        return chunks
    return []


def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    """
    Dense retrieval: embed query → query ChromaDB → trả về top_k chunks.

    Returns:
        list of {"text": str, "source": str, "score": float, "metadata": dict}
    """
    embed = _get_embedding_fn()
    query_embedding = embed(query)

    try:
        collection = _get_collection()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"],
        )

        chunks = _format_chroma_results(results)
        chunks = [c for c in chunks if c["score"] >= MIN_SCORE]
        return _filter_unknown_error_code(query, chunks)

    except Exception as e:
        print(f"WARNING: ChromaDB query failed: {e}")
        return []


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với retrieved_chunks và retrieved_sources
    """
    task = state.get("task", "")
    top_k = int(state.get("retrieval_top_k", state.get("top_k", DEFAULT_TOP_K)))

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("worker_io_logs", [])

    state["workers_called"].append(WORKER_NAME)

    # Log worker IO (theo contract)
    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "top_k": top_k},
        "output": None,
        "error": None,
    }

    try:
        chunks = retrieve_dense(task, top_k=top_k)

        sources = sorted({c["source"] for c in chunks})

        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sources

        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
        }
        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {sources}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(e)}
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    # Ghi worker IO vào state để trace
    state["worker_io_logs"].append(worker_io)

    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Retrieval Worker — Standalone Test")
    print("=" * 50)

    test_queries = [
        "SLA ticket P1 là bao lâu?",
        "Điều kiện được hoàn tiền là gì?",
        "Ai phê duyệt cấp quyền Level 3?",
        "ERR-403-AUTH là lỗi gì và cách xử lý?",
    ]

    for query in test_queries:
        print(f"\n> Query: {query}")
        result = run({"task": query})
        chunks = result.get("retrieved_chunks", [])
        print(f"  Retrieved: {len(chunks)} chunks")
        for c in chunks[:2]:
            print(f"    [{c['score']:.3f}] {c['source']}: {c['text'][:80]}...")
        print(f"  Sources: {result.get('retrieved_sources', [])}")

    print("\nOK: retrieval_worker test done.")
