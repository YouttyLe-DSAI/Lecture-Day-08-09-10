"""
graph.py — Supervisor Orchestrator
Sprint 1: Implement AgentState, supervisor_node, route_decision và kết nối graph.

Kiến trúc:
    Input → Supervisor → [retrieval_worker | policy_tool_worker | human_review] → synthesis → Output

Chạy thử:
    python graph.py

Owner: Cao (Supervisor Owner)
"""

import json
import os
import re
from datetime import datetime
from typing import TypedDict, Literal, Optional

from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────
# 1. Shared State — dữ liệu đi xuyên toàn graph
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    # Input
    task: str                           # Câu hỏi đầu vào từ user

    # Supervisor decisions
    route_reason: str                   # Lý do route sang worker nào
    risk_high: bool                     # True → cần HITL hoặc human_review
    needs_tool: bool                    # True → cần gọi external tool qua MCP
    hitl_triggered: bool                # True → đã pause cho human review

    # Worker outputs
    retrieved_chunks: list              # Output từ retrieval_worker
    retrieved_sources: list             # Danh sách nguồn tài liệu
    policy_result: dict                 # Output từ policy_tool_worker
    mcp_tools_used: list                # Danh sách MCP tools đã gọi

    # Final output
    final_answer: str                   # Câu trả lời tổng hợp
    sources: list                       # Sources được cite
    confidence: float                   # Mức độ tin cậy (0.0 - 1.0)

    # Trace & history
    history: list                       # Lịch sử các bước đã qua
    workers_called: list                # Danh sách workers đã được gọi
    supervisor_route: str               # Worker được chọn bởi supervisor
    latency_ms: Optional[int]           # Thời gian xử lý (ms)
    run_id: str                         # ID của run này


def make_initial_state(task: str) -> AgentState:
    """Khởi tạo state cho một run mới."""
    return {
        "task": task,
        "route_reason": "",
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": [],
        "workers_called": [],
        "supervisor_route": "",
        "latency_ms": None,
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    }


# ─────────────────────────────────────────────
# 2. Supervisor Node — quyết định route
# Owner: Cao
# ─────────────────────────────────────────────

def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor phân tích task và quyết định:
    1. Route sang worker nào
    2. Có cần MCP tool không
    3. Có risk cao cần HITL không
    """
    task = state["task"].lower()
    state["history"].append(f"[supervisor] received task: {state['task'][:80]}")

    route = "retrieval_worker"
    route_reason = ""
    needs_tool = False
    risk_high = False

    # ── Policy / Refund keywords ──
    policy_refund_kw = ["hoàn tiền", "refund", "flash sale", "store credit",
                        "ngoại lệ", "exception", "policy", "chính sách hoàn"]
    # ── Access Control keywords ──
    access_kw = ["cấp quyền", "access", "level 2", "level 3", "level 4",
                 "admin access", "elevated", "permission", "phê duyệt"]
    # ── SLA / Ticket keywords ──
    sla_kw = ["p1", "sla", "ticket", "escalation", "sự cố", "incident",
              "on-call", "phản hồi", "resolution"]
    # ── HR keywords ──
    hr_kw = ["remote", "nghỉ phép", "thử việc", "probation", "leave",
             "làm thêm giờ", "overtime"]
    # ── IT Helpdesk keywords ──
    it_kw = ["mật khẩu", "password", "vpn", "đăng nhập", "login",
             "tài khoản", "khóa", "helpdesk", "laptop"]
    # ── Risk keywords (may trigger HITL) ──
    risk_kw = ["emergency", "khẩn cấp", "2am", "không rõ",
               "tạm thời", "contractor"]

    # Detect multi-hop: task liên quan BOTH SLA + Access
    has_sla = any(kw in task for kw in sla_kw)
    has_access = any(kw in task for kw in access_kw)
    has_policy = any(kw in task for kw in policy_refund_kw)
    has_hr = any(kw in task for kw in hr_kw)
    has_it = any(kw in task for kw in it_kw)

    # Multi-hop detection (SLA + Access → cần cả retrieval + policy)
    if has_sla and has_access:
        route = "policy_tool_worker"
        route_reason = "multi-hop: task contains BOTH SLA and access control keywords → policy_tool_worker (will also retrieve)"
        needs_tool = True
        risk_high = True
    elif has_policy:
        route = "policy_tool_worker"
        matched = [kw for kw in policy_refund_kw if kw in task]
        route_reason = f"task contains policy/refund keywords: {matched}"
        needs_tool = True
    elif has_access:
        route = "policy_tool_worker"
        matched = [kw for kw in access_kw if kw in task]
        route_reason = f"task contains access control keywords: {matched}"
        needs_tool = True
    elif has_sla:
        route = "retrieval_worker"
        matched = [kw for kw in sla_kw if kw in task]
        route_reason = f"task contains SLA/ticket keywords: {matched}"
    elif has_hr:
        route = "retrieval_worker"
        matched = [kw for kw in hr_kw if kw in task]
        route_reason = f"task contains HR policy keywords: {matched}"
    elif has_it:
        route = "retrieval_worker"
        matched = [kw for kw in it_kw if kw in task]
        route_reason = f"task contains IT helpdesk keywords: {matched}"
    else:
        route = "retrieval_worker"
        route_reason = "no specific domain keyword matched → default retrieval"

    # Risk detection
    if any(kw in task for kw in risk_kw):
        risk_high = True
        risk_matched = [kw for kw in risk_kw if kw in task]
        route_reason += f" | risk_high flagged due to: {risk_matched}"

    # Human review override for unknown error codes
    err_pattern = re.search(r"err[-_]\d{3}", task)
    if err_pattern and risk_high:
        route = "human_review"
        route_reason = f"unknown error code '{err_pattern.group()}' + risk_high → human review"

    state["supervisor_route"] = route
    state["route_reason"] = route_reason
    state["needs_tool"] = needs_tool
    state["risk_high"] = risk_high
    state["history"].append(f"[supervisor] route={route} reason={route_reason}")

    return state


# ─────────────────────────────────────────────
# 3. Route Decision — conditional edge
# ─────────────────────────────────────────────

def route_decision(state: AgentState) -> Literal["retrieval_worker", "policy_tool_worker", "human_review"]:
    """
    Trả về tên worker tiếp theo dựa vào supervisor_route trong state.
    Đây là conditional edge của graph.
    """
    route = state.get("supervisor_route", "retrieval_worker")
    return route  # type: ignore


# ─────────────────────────────────────────────
# 4. Human Review Node — HITL placeholder
# ─────────────────────────────────────────────

def human_review_node(state: AgentState) -> AgentState:
    """
    HITL node: pause và chờ human approval.
    Trong lab này, implement dưới dạng placeholder (in ra warning).
    """
    state["hitl_triggered"] = True
    state["history"].append("[human_review] HITL triggered — awaiting human input")
    state["workers_called"].append("human_review")

    # Placeholder: tự động approve để pipeline tiếp tục
    print(f"\n⚠️  HITL TRIGGERED")
    print(f"   Task: {state['task']}")
    print(f"   Reason: {state['route_reason']}")
    print(f"   Action: Auto-approving in lab mode (set hitl_triggered=True)\n")

    # Sau khi human approve, route về retrieval để lấy evidence
    state["supervisor_route"] = "retrieval_worker"
    state["route_reason"] += " | human approved → retrieval"

    return state


# ─────────────────────────────────────────────
# 5. Import Workers — REAL implementations
# Owner: Ly (Worker Owner)
# ─────────────────────────────────────────────

from workers.retrieval import run as retrieval_run
from workers.policy_tool import run as policy_tool_run
from workers.synthesis import run as synthesis_run


def retrieval_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi retrieval worker thật."""
    state = retrieval_run(state)
    return state


def policy_tool_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi policy/tool worker thật."""
    state = policy_tool_run(state)
    return state


def synthesis_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi synthesis worker thật."""
    state = synthesis_run(state)
    return state


# ─────────────────────────────────────────────
# 6. Build Graph
# Owner: Cao
# ─────────────────────────────────────────────

def build_graph():
    """
    Xây dựng graph với supervisor-worker pattern.
    Option A (đơn giản — Python thuần): Dùng if/else, không cần LangGraph.
    """
    def run(state: AgentState) -> AgentState:
        import time
        start = time.time()

        # Step 1: Supervisor decides route
        state = supervisor_node(state)

        # Step 2: Route to appropriate worker
        route = route_decision(state)

        if route == "human_review":
            state = human_review_node(state)
            # After human approval, continue with retrieval
            state = retrieval_worker_node(state)
        elif route == "policy_tool_worker":
            # Policy worker cần retrieval context trước
            state = retrieval_worker_node(state)
            state = policy_tool_worker_node(state)
        else:
            # Default: retrieval_worker
            state = retrieval_worker_node(state)

        # Step 3: Always synthesize
        state = synthesis_worker_node(state)

        state["latency_ms"] = int((time.time() - start) * 1000)
        state["history"].append(f"[graph] completed in {state['latency_ms']}ms")
        return state

    return run


# ─────────────────────────────────────────────
# 7. Public API
# ─────────────────────────────────────────────

_graph = build_graph()


def run_graph(task: str) -> AgentState:
    """
    Entry point: nhận câu hỏi, trả về AgentState với full trace.

    Args:
        task: Câu hỏi từ user

    Returns:
        AgentState với final_answer, trace, routing info, v.v.
    """
    state = make_initial_state(task)
    result = _graph(state)
    return result


def save_trace(state: AgentState, output_dir: str = "./artifacts/traces") -> str:
    """Lưu trace ra file JSON."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/{state['run_id']}.json"
    # Serialize-safe copy
    safe_state = {}
    for k, v in state.items():
        try:
            json.dumps(v, ensure_ascii=False)
            safe_state[k] = v
        except (TypeError, ValueError):
            safe_state[k] = str(v)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(safe_state, f, ensure_ascii=False, indent=2)
    return filename


# ─────────────────────────────────────────────
# 8. Manual Test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Day 09 Lab — Supervisor-Worker Graph")
    print("=" * 60)

    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
        "Ticket P1 lúc 2am. Cần cấp Level 2 access tạm thời cho contractor. Nêu đủ cả hai quy trình.",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run_graph(query)
        print(f"  Route   : {result['supervisor_route']}")
        print(f"  Reason  : {result['route_reason']}")
        print(f"  Workers : {result['workers_called']}")
        print(f"  Answer  : {result['final_answer'][:150]}...")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Latency : {result['latency_ms']}ms")
        print(f"  Sources : {result.get('retrieved_sources', [])}")

        # Lưu trace
        trace_file = save_trace(result)
        print(f"  Trace saved → {trace_file}")

    print("\n✅ graph.py test complete.")
