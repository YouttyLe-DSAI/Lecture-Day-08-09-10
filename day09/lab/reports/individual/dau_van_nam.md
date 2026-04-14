# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nam 
**Vai trò trong nhóm:** Supervisor Owner  
**Ngày nộp:** 2026-04-14  

---

## 1. Tôi phụ trách phần nào?

**Module/file tôi chịu trách nhiệm:**
- File chính: `graph.py`
- Functions tôi implement: `supervisor_node()`, `route_decision()`, `human_review_node()`, `build_graph()`, `run_graph()`, `save_trace()`, `make_initial_state()`

Tôi chịu trách nhiệm toàn bộ Sprint 1 — xây dựng orchestrator graph từ scratch. Cụ thể, tôi thiết kế `AgentState` TypedDict với 16 fields (task, route_reason, risk_high, needs_tool, retrieved_chunks, policy_result, final_answer, confidence, v.v.), implement routing logic trong `supervisor_node()` với 6 bộ keyword lists, và kết nối workers thành pipeline: supervisor → route_decision → [retrieval | policy_tool | human_review] → synthesis → output.

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`graph.py` import trực tiếp `workers.retrieval.run`, `workers.policy_tool.run`, `workers.synthesis.run` — interface của Ly. MCP integration của Cao được gọi gián tiếp qua policy_tool worker. Tuấn dùng `run_graph()` và `save_trace()` trong eval_trace.py.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Implement multi-hop detection trong supervisor_node — khi task chứa BOTH SLA keywords VÀ access control keywords, tự động route sang policy_tool_worker + gọi retrieval trước.

**Lý do:**

Câu q15 ("Ticket P1 lúc 2am. Cần cấp Level 2 access tạm thời...") yêu cầu cross-reference 2 documents: sla_p1_2026.txt VÀ access_control_sop.txt. Nếu chỉ route sang retrieval_worker, pipeline chỉ retrieve từ 1 doc. Bằng cách detect overlap keywords (has_sla AND has_access), supervisor route sang policy_tool_worker, worker này gọi MCP check_access_permission VÀ retrieval cho cả 2 domains.

**Trade-off đã chấp nhận:**

Multi-hop detection dựa vào keyword overlap → có thể false positive nếu task mention cả 2 domains nhưng chỉ cần 1. Tuy nhiên, trong lab này, tất cả multi-hop cases đều genuine → accuracy 100% (2/2).

**Bằng chứng từ trace/code:**

```json
// Trace q15 — multi-hop detection
{
  "task": "Ticket P1 lúc 2am. Cần cấp Level 2 access tạm thời cho contractor...",
  "supervisor_route": "policy_tool_worker",
  "route_reason": "multi-hop: task contains BOTH SLA and access control keywords → policy_tool_worker (will also retrieve) | risk_high flagged due to: ['2am', 'tạm thời', 'contractor']",
  "workers_called": ["retrieval_worker", "policy_tool_worker", "synthesis_worker"],
  "mcp_tools_used": ["get_ticket_info", "check_access_permission"],
  "retrieved_sources": ["access_control_sop.txt", "sla_p1_2026.txt"],
  "confidence": 0.68
}
```

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** Ban đầu, routing logic chỉ dùng if/elif chain — khi task chứa cả SLA + access keywords, chỉ match condition đầu tiên (SLA → retrieval_worker), bỏ qua access context.

**Symptom:** Câu q15 chỉ trả lời phần SLA (escalation timeline) mà thiếu phần access permission (Level 2 emergency bypass).

**Root cause:** if/elif là exclusive — `if has_sla` match trước `elif has_access`, nên access keywords bị skip.

**Cách sửa:** Thêm multi-hop detection ở đầu chain: `if has_sla and has_access` → route policy_tool_worker + needs_tool=True. Đặt condition này TRƯỚC các single-domain checks.

**Bằng chứng trước/sau:**

Trước: q15 → `route: retrieval_worker`, `sources: ['sla_p1_2026.txt']` — chỉ 1 doc  
Sau: q15 → `route: policy_tool_worker`, `sources: ['access_control_sop.txt', 'sla_p1_2026.txt']` — cả 2 docs + 2 MCP tools

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**

Thiết kế routing logic rõ ràng — route_reason messages chi tiết đủ để debug từ trace mà không cần đọc code. Multi-hop detection là contribution lớn nhất giúp q13, q15 pass.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

ERR-403-AUTH regex pattern quá strict (chỉ match `err-\d{3}`), miss câu q09. Nên dùng broader pattern hoặc LLM classifier cho edge cases.

**Nhóm phụ thuộc vào tôi ở đâu?**

Toàn bộ worker integration — nếu graph.py chưa connect workers, Ly không thể test end-to-end. AgentState schema ảnh hưởng tất cả workers.

**Phần tôi phụ thuộc vào thành viên khác:**

Workers run() functions từ Ly — tôi cần interface match contracts. MCP dispatch_tool() từ Cao.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ thêm **LLM-based routing fallback** cho câu mà keyword matching miss (confidence < 0.3 sau retrieval). Mặc dù nhóm đã kịp hoàn thành MCP HTTP server (bonus +2), việc routing vẫn có thể thông minh hơn bằng LLM để handle edge cases như q09.

---

