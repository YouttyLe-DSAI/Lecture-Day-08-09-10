"""
workers/synthesis.py — Synthesis Worker
Owner: Ly (Worker Owner)
Sprint 2: Tổng hợp câu trả lời từ retrieved_chunks và policy_result.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: evidence từ retrieval_worker
    - policy_result: kết quả từ policy_tool_worker

Output (vào AgentState):
    - final_answer: câu trả lời cuối với citation
    - sources: danh sách nguồn tài liệu được cite
    - confidence: mức độ tin cậy (0.0 - 1.0)

Gọi độc lập để test:
    python workers/synthesis.py
"""

import os
import sys

# Fix Windows encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

WORKER_NAME = "synthesis_worker"

SYSTEM_PROMPT = """Bạn là trợ lý IT Helpdesk nội bộ.

Quy tắc nghiêm ngặt:
1. CHỈ trả lời dựa vào context được cung cấp. KHÔNG dùng kiến thức ngoài.
2. Nếu context không đủ để trả lời → nói rõ "Không đủ thông tin trong tài liệu nội bộ".
3. Trích dẫn nguồn cuối mỗi câu quan trọng: [tên_file].
4. Trả lời súc tích, có cấu trúc. Không dài dòng.
5. Nếu có exceptions/ngoại lệ → nêu rõ ràng trước khi kết luận.
"""


def _call_llm(messages: list, chunks: list = None, policy_result: dict = None) -> str:
    """
    Gọi LLM để tổng hợp câu trả lời.
    Fallback: trích xuất câu trả lời trực tiếp từ context nếu không có LLM.
    """
    # Option A: OpenAI
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key and not openai_key.startswith("sk-..."):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.1,
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception:
            pass

    # Option B: Gemini
    google_key = os.getenv("GOOGLE_API_KEY", "")
    if google_key and not google_key.startswith("AI..."):
        try:
            import google.generativeai as genai
            genai.configure(api_key=google_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            combined = "\n".join([m["content"] for m in messages])
            response = model.generate_content(combined)
            return response.text
        except Exception:
            pass

    # Fallback: Context-based extraction (no hallucination)
    return _extract_answer_from_context(chunks or [], policy_result or {})


def _extract_answer_from_context(chunks: list, policy_result: dict) -> str:
    """
    Trích xuất câu trả lời trực tiếp từ context khi không có LLM.
    Đảm bảo grounded — chỉ dùng thông tin từ chunks.
    """
    if not chunks:
        return "Không đủ thông tin trong tài liệu nội bộ để trả lời câu hỏi này."
    
    parts = []
    sources_cited = set()
    
    # Add relevant chunks as evidence
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source", "unknown")
        text = chunk.get("text", "").strip()
        if text:
            parts.append(f"[{i}] {text}")
            sources_cited.add(source)
    
    # Add policy exceptions if any
    if policy_result.get("exceptions_found"):
        parts.append("\nNgoai le phat hien:")
        for ex in policy_result["exceptions_found"]:
            parts.append(f"- {ex.get('rule', '')}")
    
    # Add policy version note if any
    if policy_result.get("policy_version_note"):
        parts.append(f"\nLuu y: {policy_result['policy_version_note']}")
    
    # Add access check results if any
    if policy_result.get("access_check"):
        ac = policy_result["access_check"]
        parts.append(f"\nKet qua kiem tra quyen truy cap:")
        parts.append(f"- Access level: {ac.get('access_level', '?')}")
        parts.append(f"- Can grant: {ac.get('can_grant', '?')}")
        parts.append(f"- Required approvers: {ac.get('required_approvers', [])}")
        parts.append(f"- Emergency override: {ac.get('emergency_override', False)}")
        if ac.get("notes"):
            for note in ac["notes"]:
                parts.append(f"- {note}")
    
    # Citation footer
    if sources_cited:
        parts.append(f"\nNguon: {', '.join(sorted(sources_cited))}")
    
    return "\n".join(parts)


def _build_context(chunks: list, policy_result: dict) -> str:
    """Xây dựng context string từ chunks và policy result."""
    parts = []

    if chunks:
        parts.append("=== TÀI LIỆU THAM KHẢO ===")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            score = chunk.get("score", 0)
            parts.append(f"[{i}] Nguồn: {source} (relevance: {score:.2f})\n{text}")

    if policy_result and policy_result.get("exceptions_found"):
        parts.append("\n=== POLICY EXCEPTIONS ===")
        for ex in policy_result["exceptions_found"]:
            parts.append(f"- {ex.get('rule', '')}")

    if not parts:
        return "(Không có context)"

    return "\n\n".join(parts)


def _estimate_confidence(chunks: list, answer: str, policy_result: dict) -> float:
    """
    Ước tính confidence dựa vào:
    - Số lượng và quality của chunks
    - Có exceptions không
    - Answer có abstain không

    Note: Current version uses heuristic scoring. LLM-as-Judge is an optional enhancement.
    """
    if not chunks:
        return 0.1  # Không có evidence → low confidence

    if "Không đủ thông tin" in answer or "không có trong tài liệu" in answer.lower():
        return 0.3  # Abstain → moderate-low

    # Weighted average của chunk scores
    if chunks:
        avg_score = sum(c.get("score", 0) for c in chunks) / len(chunks)
    else:
        avg_score = 0

    # Penalty nếu có exceptions (phức tạp hơn)
    exception_penalty = 0.05 * len(policy_result.get("exceptions_found", []))

    confidence = min(0.95, avg_score - exception_penalty)
    return round(max(0.1, confidence), 2)


def synthesize(task: str, chunks: list, policy_result: dict) -> dict:
    """
    Tổng hợp câu trả lời từ chunks và policy context.

    Returns:
        {"answer": str, "sources": list, "confidence": float}
    """
    context = _build_context(chunks, policy_result)

    # Build messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Câu hỏi: {task}

{context}

Hãy trả lời câu hỏi dựa vào tài liệu trên."""
        }
    ]

    answer = _call_llm(messages, chunks=chunks, policy_result=policy_result)
    sources = list({c.get("source", "unknown") for c in chunks})
    confidence = _estimate_confidence(chunks, answer, policy_result)

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
    }


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {})

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "has_policy": bool(policy_result),
        },
        "output": None,
        "error": None,
    }

    try:
        result = synthesize(task, chunks, policy_result)
        state["final_answer"] = result["answer"]
        state["sources"] = result["sources"]
        state["confidence"] = result["confidence"]

        worker_io["output"] = {
            "answer_length": len(result["answer"]),
            "sources": result["sources"],
            "confidence": result["confidence"],
        }
        state["history"].append(
            f"[{WORKER_NAME}] answer generated, confidence={result['confidence']}, "
            f"sources={result['sources']}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "SYNTHESIS_FAILED", "reason": str(e)}
        state["final_answer"] = f"SYNTHESIS_ERROR: {e}"
        state["confidence"] = 0.0
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Synthesis Worker — Standalone Test")
    print("=" * 50)

    test_state = {
        "task": "SLA ticket P1 là bao lâu?",
        "retrieved_chunks": [
            {
                "text": "Ticket P1: Phản hồi ban đầu 15 phút kể từ khi ticket được tạo. Xử lý và khắc phục 4 giờ. Escalation: tự động escalate lên Senior Engineer nếu không có phản hồi trong 10 phút.",
                "source": "sla_p1_2026.txt",
                "score": 0.92,
            }
        ],
        "policy_result": {},
    }

    result = run(test_state.copy())
    print(f"\nAnswer:\n{result['final_answer']}")
    print(f"\nSources: {result['sources']}")
    print(f"Confidence: {result['confidence']}")

    print("\n--- Test 2: Exception case ---")
    test_state2 = {
        "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì lỗi nhà sản xuất.",
        "retrieved_chunks": [
            {
                "text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền theo Điều 3 chính sách v4.",
                "source": "policy_refund_v4.txt",
                "score": 0.88,
            }
        ],
        "policy_result": {
            "policy_applies": False,
            "exceptions_found": [{"type": "flash_sale_exception", "rule": "Flash Sale không được hoàn tiền."}],
        },
    }
    result2 = run(test_state2.copy())
    print(f"\nAnswer:\n{result2['final_answer']}")
    print(f"Confidence: {result2['confidence']}")

    print("\n✅ synthesis_worker test done.")
