# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nam  
**Vai trò trong nhóm:** MCP Owner  
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

**Module/file tôi chịu trách nhiệm:**
- File chính: `mcp_server.py`, phần MCP integration trong `workers/policy_tool.py`
- Functions tôi implement: `tool_search_kb()`, `tool_get_ticket_info()`, `tool_check_access_permission()`, `tool_create_ticket()`, `dispatch_tool()`, `list_tools()`, `_call_mcp_tool()` (trong policy_tool.py)

Tôi chịu trách nhiệm Sprint 3 — xây dựng MCP server và tích hợp MCP client vào policy_tool worker. MCP server expose 4 tools qua `dispatch_tool()` interface, mỗi tool có schema định nghĩa (TOOL_SCHEMAS) giống MCP protocol thật. `search_kb` kết nối ChromaDB qua retrieval worker. `get_ticket_info` trả về mock ticket data (P1-LATEST, IT-1234). `check_access_permission` kiểm tra access rules cho Level 1/2/3 với emergency bypass logic. `create_ticket` tạo mock ticket.

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`dispatch_tool()` được gọi từ `_call_mcp_tool()` trong policy_tool.py (Ly). MCP tool results được ghi vào `state["mcp_tools_used"]` — Tuấn trace format này trong eval_trace.py. TOOL_SCHEMAS match với contracts YAML.

**Bằng chứng:** Xem comment `# Owner: Nam (MCP Owner)` trong policy_tool.py dòng 3.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Implement emergency bypass logic trong `check_access_permission` — Level 2 CÓ emergency bypass (cấp tạm với Line Manager + IT Admin on-call), Level 3 KHÔNG CÓ.

**Lý do:**

Theo access_control_sop.txt Section 4: "On-call IT Admin có thể cấp quyền tạm thời (max 24 giờ) sau khi được Tech Lead phê duyệt bằng lời." Tuy nhiên, đây chỉ áp dụng cho một số levels. Tôi thiết kế ACCESS_RULES dict với `emergency_can_bypass: True/False` theo từng level. Level 2 có bypass (phổ biến cho incident fix), Level 3 (Admin) KHÔNG có bypass vì risk quá cao.

Lựa chọn thay thế: cho tất cả levels đều có emergency bypass — nhưng điều này contradicts SOP ("Level 4 — Admin Access" yêu cầu "Training bắt buộc về security policy").

**Trade-off đã chấp nhận:**

Rule cứng (hardcoded) — nếu SOP thay đổi, phải sửa code. Trong production nên đọc rules từ config file hoặc database.

**Bằng chứng từ trace/code:**

```python
# mcp_server.py — ACCESS_RULES
ACCESS_RULES = {
    2: {"required_approvers": ["Line Manager", "IT Admin"], 
        "emergency_can_bypass": True,
        "emergency_bypass_note": "Level 2 có thể cấp tạm thời với approval đồng thời..."},
    3: {"required_approvers": ["Line Manager", "IT Admin", "IT Security"],
        "emergency_can_bypass": False,
        "note": "Admin access — không có emergency bypass"},
}
```

Trace q15: `check_access_permission(level=2, emergency=True)` → `"emergency_override": true, "can_grant": true`  
Trace q13: `check_access_permission(level=3, emergency=True)` → `"emergency_override": false`, notes: "Level 3 KHÔNG có emergency bypass"

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** `dispatch_tool()` raise TypeError khi tool_input thiếu optional parameter — VD: `check_access_permission` gọi không có `is_emergency` → crash.

**Symptom:** Pipeline crash với `TypeError: check_access_permission() missing required argument: 'is_emergency'` khi policy_tool gọi MCP mà không truyền `is_emergency`.

**Root cause:** `tool_fn(**tool_input)` spread tất cả keys — nếu `is_emergency` không có trong input dict, function crash vì Python function signature chưa set default.

**Cách sửa:** Thêm default value `is_emergency: bool = False` trong `tool_check_access_permission()` function signature. Đồng thời, `dispatch_tool()` đã có try/except TypeError → trả về error dict thay vì crash. Double defense.

**Bằng chứng trước/sau:**

Trước: `dispatch_tool("check_access_permission", {"access_level": 3, "requester_role": "contractor"})` → TypeError crash  
Sau: Cùng call → trả về `{"can_grant": true, "required_approvers": [...], "emergency_override": false}` — is_emergency defaults to False

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**

MCP dispatch layer design — `dispatch_tool()` handle mọi error gracefully (không raise exception ra ngoài), có TOOL_SCHEMAS cho discovery, và log mọi call với timestamp. 4 tools cover đủ use cases của lab.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

MCP server vẫn là mock class (in-process), chưa implement HTTP server thật. Nếu có thêm thời gian, sẽ dùng FastAPI + uvicorn để earn bonus +2.

**Nhóm phụ thuộc vào tôi ở đâu?**

Policy tool worker gọi MCP tools — nếu `dispatch_tool()` fail, policy analysis thiếu access check results. Multi-hop answers (q13, q15) phụ thuộc MCP `check_access_permission`.

**Phần tôi phụ thuộc vào thành viên khác:**

`retrieve_dense()` từ retrieval worker (Ly) — `search_kb` tool delegate sang retrieval. State schema từ Cao.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ implement **real MCP HTTP server** bằng FastAPI + uvicorn (`python mcp_server.py --http --port 8080`). Lý do: trace hiện tại ghi `mcp_tool_called` nhưng latency gần 0ms vì in-process — HTTP server sẽ cho latency thực tế và test deployment independence. Bonus +2 điểm theo SCORING.md.

---

*Lưu file này với tên: `reports/individual/nam.md`*
