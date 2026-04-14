"""
workers/policy_tool.py — Policy & Tool Worker
Sprint 2+3: Kiểm tra policy dựa vào context, gọi MCP tools khi cần.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: context từ retrieval_worker
    - needs_tool: True nếu supervisor quyết định cần tool call

Output (vào AgentState):
    - policy_result: {"policy_applies", "policy_name", "exceptions_found", "source", "rule"}
    - mcp_tools_used: list of tool calls đã thực hiện
    - worker_io_log: log

Gọi độc lập để test:
    python workers/policy_tool.py
"""

import os
import re
import sys
import unicodedata
from datetime import datetime
from typing import Optional


WORKER_NAME = "policy_tool_worker"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _norm(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-zA-Z0-9:/#@._+-]+", " ", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def _has(text: str, *keywords: str) -> bool:
    normalized = _norm(text)
    return any(_norm(keyword) in normalized for keyword in keywords)


def _is_not_flash_sale(task: str) -> bool:
    normalized = _norm(task)
    if not _has(task, "flash sale"):
        return False
    if _has(task, "không phải flash sale", "khong phai flash sale", "not flash sale"):
        return True

    # Be tolerant of mojibake from shell input, e.g. "khÃ´ng pháº£i".
    has_negation = bool(re.search(r"\b(khong|kh ng|kha ng)\b", normalized))
    has_phai = bool(re.search(r"\b(phai|ph i|pha i)\b", normalized))
    return has_negation and has_phai and "flash sale" in normalized


def _access_level(task: str) -> Optional[int]:
    normalized = _norm(task)
    match = re.search(r"\blevel\s*([1-4])\b", normalized)
    if match:
        level = int(match.group(1))
        return 3 if level == 4 else level
    if "admin access" in normalized or "admin" in normalized:
        return 3
    return None


def _needs_ticket_info(task: str) -> bool:
    if _has(task, "ticket", "jira"):
        return True
    if not _has(task, "p1"):
        return False
    if _access_level(task) is not None or _has(task, "access", "cấp quyền", "cap quyen"):
        return False
    return _has(
        task,
        "sla",
        "incident",
        "status",
        "trạng thái",
        "trang thai",
        "bao lâu",
        "bao lau",
        "thời gian",
        "thoi gian",
        "deadline",
        "resolution",
        "resolve",
    )


def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Gọi MCP tool qua mock in-process server.
    """
    try:
        lab_dir = os.path.dirname(os.path.dirname(__file__))
        if lab_dir not in sys.path:
            sys.path.insert(0, lab_dir)
        from mcp_server import dispatch_tool

        result = dispatch_tool(tool_name, tool_input)
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": result,
            "error": None,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": None,
            "error": {"code": "MCP_CALL_FAILED", "reason": str(e)},
            "timestamp": datetime.now().isoformat(),
        }


def analyze_policy(task: str, chunks: list) -> dict:
    """
    Rule-based policy analysis, intentionally compact.
    """
    exceptions_found = []

    # Refund exception facts must come from the task, not merely from a policy doc
    # chunk that lists all possible exceptions.
    if _has(task, "flash sale") and not _is_not_flash_sale(task):
        exceptions_found.append({
            "type": "flash_sale_exception",
            "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
            "source": "policy_refund_v4.txt",
        })

    if _has(task, "license key", "license", "subscription", "kỹ thuật số", "digital product"):
        exceptions_found.append({
            "type": "digital_product_exception",
            "rule": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    if not _has(task, "chưa kích hoạt", "chua kich hoat", "chưa sử dụng", "chua su dung", "chưa dùng"):
        if _has(task, "đã kích hoạt", "da kich hoat", "đã đăng ký", "đã sử dụng", "activated"):
            exceptions_found.append({
                "type": "activated_exception",
                "rule": "Sản phẩm đã kích hoạt hoặc đăng ký tài khoản không được hoàn tiền (Điều 3).",
                "source": "policy_refund_v4.txt",
            })

    policy_name = "refund_policy_v4"
    policy_version_note = ""
    if _has(task, "31/01", "30/01", "trước 01/02", "truoc 01/02", "before 01/02"):
        policy_version_note = "Đơn hàng đặt trước 01/02/2026 áp dụng chính sách v3 (không có trong tài liệu hiện tại)."

    access_result = None
    level = _access_level(task)
    if level is not None or _has(task, "cấp quyền", "cap quyen", "access", "contractor", "admin"):
        policy_name = "access_control_sop"
        policy_version_note = ""
        emergency = _has(task, "emergency", "khẩn cấp", "khan cap", "p1", "incident", "2am", "active")
        if level == 2:
            access_result = {
                "access_level": 2,
                "required_approvers": ["Line Manager", "IT Admin"],
                "emergency_override_allowed": emergency,
                "rule": "Level 2 cần Line Manager + IT Admin; emergency có thể cấp tạm thời khi được phê duyệt đồng thời.",
                "source": "access_control_sop.txt",
            }
        elif level == 3:
            access_result = {
                "access_level": 3,
                "required_approvers": ["Line Manager", "IT Admin", "IT Security"],
                "emergency_override_allowed": False,
                "rule": "Level 3 cần Line Manager + IT Admin + IT Security; không cấp tạm thời nếu thiếu phê duyệt.",
                "source": "access_control_sop.txt",
            }

    policy_applies = len(exceptions_found) == 0 and not policy_version_note
    if access_result:
        emergency = _has(task, "emergency", "khẩn cấp", "khan cap", "p1", "incident", "2am", "active")
        policy_applies = not (emergency and not access_result["emergency_override_allowed"])

    sources = sorted({c.get("source", "unknown") for c in chunks if c})
    for ex in exceptions_found:
        if ex["source"] not in sources:
            sources.append(ex["source"])
    if access_result and access_result["source"] not in sources:
        sources.append(access_result["source"])

    return {
        "policy_applies": policy_applies,
        "policy_name": policy_name,
        "exceptions_found": exceptions_found,
        "source": sources,
        "policy_version_note": policy_version_note,
        "access_result": access_result,
        "rule": access_result.get("rule") if access_result else "",
        "explanation": "Analyzed via compact rule-based policy check.",
    }


def run(state: dict) -> dict:
    """
    Worker entry point - gọi từ graph.py hoặc test độc lập.
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    needs_tool = state.get("needs_tool", False)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])
    state.setdefault("worker_io_logs", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "chunks_count": len(chunks), "needs_tool": needs_tool},
        "output": None,
        "error": None,
    }

    try:
        if not chunks and needs_tool:
            mcp_result = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
            state["mcp_tools_used"].append(mcp_result)
            state["mcp_tool_called"] = mcp_result["tool"]
            state["mcp_result"] = mcp_result.get("output")
            state["history"].append(f"[{WORKER_NAME}] called MCP search_kb")
            chunks = (mcp_result.get("output") or {}).get("chunks", [])
            state["retrieved_chunks"] = chunks
            state["retrieved_sources"] = sorted({c.get("source", "unknown") for c in chunks})

        policy_result = analyze_policy(task, chunks)
        level = _access_level(task)
        if level is not None and needs_tool:
            mcp_result = _call_mcp_tool("check_access_permission", {
                "access_level": level,
                "requester_role": "contractor" if _has(task, "contractor") else "employee",
                "is_emergency": _has(task, "emergency", "khẩn cấp", "p1", "2am", "active"),
            })
            state["mcp_tools_used"].append(mcp_result)
            state["mcp_tool_called"] = mcp_result["tool"]
            state["mcp_result"] = mcp_result.get("output")
            state["history"].append(f"[{WORKER_NAME}] called MCP check_access_permission")
            if mcp_result.get("output") and not mcp_result.get("error"):
                policy_result["access_result_mcp"] = mcp_result["output"]

        if needs_tool and _needs_ticket_info(task):
            mcp_result = _call_mcp_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
            state["mcp_tools_used"].append(mcp_result)
            state["mcp_tool_called"] = mcp_result["tool"]
            state["mcp_result"] = mcp_result.get("output")
            state["history"].append(f"[{WORKER_NAME}] called MCP get_ticket_info")

        state["policy_result"] = policy_result
        worker_io["output"] = {
            "policy_applies": policy_result["policy_applies"],
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
            "mcp_calls": len(state.get("mcp_tools_used", [])),
        }
        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={policy_result['policy_applies']}, "
            f"exceptions={len(policy_result.get('exceptions_found', []))}"
        )
    except Exception as e:
        worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(e)}
        state["policy_result"] = {"error": str(e)}
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state["worker_io_logs"].append(worker_io)
    return state


if __name__ == "__main__":
    print("=" * 50)
    print("Policy Tool Worker — Standalone Test")
    print("=" * 50)

    test_cases = [
        {
            "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
            "retrieved_chunks": [
                {"text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.9}
            ],
        },
        {
            "task": "Khách hàng muốn hoàn tiền license key đã kích hoạt.",
            "retrieved_chunks": [
                {"text": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.88}
            ],
        },
        {
            "task": "Khách hàng yêu cầu hoàn tiền trong 5 ngày, sản phẩm lỗi, chưa kích hoạt.",
            "retrieved_chunks": [
                {"text": "Yêu cầu trong 7 ngày làm việc, sản phẩm lỗi nhà sản xuất, chưa dùng.", "source": "policy_refund_v4.txt", "score": 0.85}
            ],
        },
        {
            "task": "Contractor cần Level 2 access tạm thời để xử lý P1 emergency.",
            "needs_tool": True,
            "retrieved_chunks": [
                {"text": "Level 2 cần Line Manager + IT Admin.", "source": "access_control_sop.txt", "score": 0.85}
            ],
        },
    ]

    for tc in test_cases:
        print(f"\n> Task: {tc['task'][:70]}...")
        result = run(tc.copy())
        pr = result.get("policy_result", {})
        print(f"  policy_applies: {pr.get('policy_applies')}")
        if pr.get("exceptions_found"):
            for ex in pr["exceptions_found"]:
                print(f"  exception: {ex['type']} - {ex['rule'][:60]}...")
        print(f"  MCP calls: {len(result.get('mcp_tools_used', []))}")

    print("\nOK: policy_tool_worker test done.")
