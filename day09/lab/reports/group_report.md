# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Cao - Ly - Nam - Tuấn  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Cao | Supervisor Owner | cao@student |
| Ly | Worker Owner | ly@student |
| Nam | MCP Owner | nam@student |
| Tuấn | Trace & Docs Owner | tuan@student |

**Ngày nộp:** 2026-04-14  
**Độ dài khuyến nghị:** 600–1000 từ

---

## 1. Kiến trúc nhóm đã xây dựng

**Hệ thống tổng quan:**

Nhóm xây dựng hệ thống Supervisor-Worker với 3 workers (retrieval, policy_tool, synthesis), 1 MCP server (4 tools), và Python-based orchestrator (không dùng LangGraph). Supervisor dùng keyword-based routing để phân loại task vào 6 categories: SLA/ticket, policy/refund, access control, HR, IT helpdesk, và unknown. Khi detect multi-hop (SLA + access keywords cùng lúc), supervisor route sang policy_tool_worker và gọi thêm retrieval + MCP tools.

**Routing logic cốt lõi:**

Supervisor sử dụng keyword matching với 6 bộ keyword lists. Logic ưu tiên: (1) Multi-hop detection — nếu task chứa BOTH SLA + access keywords → policy_tool_worker. (2) Policy/refund → policy_tool_worker. (3) Access control → policy_tool_worker. (4) SLA/ticket → retrieval_worker. (5) HR/IT → retrieval_worker. (6) Default → retrieval_worker. Risk detection: emergency, 2am, contractor → flag `risk_high=True`.

**MCP tools đã tích hợp:**
- `search_kb`: Tìm kiếm KB qua ChromaDB — dùng khi policy_tool cần context nhưng chưa có chunks
- `get_ticket_info`: Tra cứu ticket P1-LATEST — trả về priority, notifications, escalation info
- `check_access_permission`: Kiểm tra access level 1/2/3 + emergency bypass rules
- `create_ticket`: Tạo ticket mới (mock) — không gọi trong test nhưng sẵn sàng

---

## 2. Quyết định kỹ thuật quan trọng nhất

**Quyết định:** Dùng keyword-based routing thay vì LLM classifier trong supervisor_node

**Bối cảnh vấn đề:**

Supervisor cần classify task vào worker phù hợp. Hai lựa chọn: (a) gọi LLM để classify intent, (b) dùng keyword matching rules.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| LLM classifier (gpt-4o-mini) | Chính xác hơn cho câu ambiguous, xử lý ngôn ngữ tự nhiên tốt | Thêm ~800ms latency per query, tốn token, cần API key |
| Keyword matching (rule-based) | Nhanh (~5ms), deterministic, không cần API key, dễ debug | Không handle được câu hỏi không chứa keyword rõ ràng |

**Phương án đã chọn và lý do:**

Chọn keyword matching vì: (1) Lab chỉ có 5 categories rõ ràng → keywords đủ cover 87% (13/15) câu test. (2) Latency thấp hơn 160x (5ms vs 800ms). (3) Deterministic → route_reason rõ ràng trong trace. (4) Không phụ thuộc API key → pipeline chạy được offline.

**Bằng chứng từ trace/code:**

```json
{
  "supervisor_route": "policy_tool_worker",
  "route_reason": "multi-hop: task contains BOTH SLA and access control keywords → policy_tool_worker (will also retrieve) | risk_high flagged due to: ['2am', 'tạm thời', 'contractor']",
  "workers_called": ["retrieval_worker", "policy_tool_worker", "synthesis_worker"],
  "confidence": 0.68,
  "latency_ms": 5551
}
```

---

## 3. Kết quả grading questions

> Chưa có grading_questions.json (public lúc 17:00), nhóm sẽ cập nhật sau khi chạy.

**Tổng điểm raw ước tính:** ___ / 96

**Câu pipeline xử lý tốt nhất:**
- ID: q06 — Lý do tốt: "P1 không phản hồi 10 phút" — retrieval_worker retrieve đúng sla_p1_2026.txt, confidence = 0.73 (cao nhất)

**Câu pipeline fail hoặc partial:**
- ID: q09 — Fail ở đâu: ERR-403-AUTH route sang retrieval_worker (default) thay vì human_review  
  Root cause: regex pattern chỉ match `err-\d{3}`, không match `ERR-403-AUTH` vì có thêm "-AUTH"

**Câu gq07 (abstain):** Pipeline sẽ trả về "Không đủ thông tin trong tài liệu nội bộ" khi confidence thấp + chunks không liên quan. Context-based fallback đảm bảo không hallucinate.

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 3 workers (retrieval + policy_tool + synthesis) + 2 MCP tools (get_ticket_info, check_access_permission). Sources: ['access_control_sop.txt', 'sla_p1_2026.txt'].

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được

**Metric thay đổi rõ nhất (có số liệu):**

| Metric | Day 09 value |
|--------|-------------|
| Avg confidence | 0.605 |
| Routing distribution | retrieval 53%, policy 47% |
| MCP usage | 20% (4/20 traces) |
| Multi-hop success | 2/2 (100%) |

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**

Multi-hop detection bằng keyword overlap đơn giản nhưng hiệu quả bất ngờ. Khi task chứa BOTH "P1" + "Level 2 access" → supervisor tự động gọi cả retrieval + policy + 2 MCP tools. Single-agent không thể phân biệt được.

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**

Câu hỏi đơn giản như "SLA P1 bao lâu?" — multi-agent thêm overhead ~3s (worker chaining) nhưng answer quality không khác so với single RAG call.

---

## 5. Phân công và đánh giá nhóm

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Cao | `graph.py` — supervisor_node, routing logic, state management, graph orchestration | Sprint 1 |
| Ly | `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py` — worker implementations | Sprint 2 |
| Nam | `mcp_server.py` — 4 MCP tools, dispatch layer, MCP integration trong policy_tool | Sprint 3 |
| Tuấn | `eval_trace.py`, docs templates, group_report, individual reports coordination | Sprint 4 |

**Điều nhóm làm tốt:**

Phân chia rõ ràng theo Sprint → không bị block lẫn nhau. Worker contracts (YAML) giúp define interface trước khi code → integration smooth.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**

Embedding model load chậm (~22s lần đầu) gây confusion khi test. Nên cache model globally thay vì load mới mỗi worker call.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**

Define contracts YAML chi tiết hơn (bao gồm cả error handling scenarios), và viết unit test cho từng worker trước khi integrate vào graph.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì?

1. **Upgrade routing sang LLM classifier** — trace q09 cho thấy keyword matching miss câu ERR-403-AUTH. LLM classifier sẽ handle ambiguous queries tốt hơn, trade-off latency +800ms nhưng accuracy tăng.
2. **Implement real MCP HTTP server** — dùng FastAPI + uvicorn để decouple tools deployment, earn bonus +2 điểm.

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
