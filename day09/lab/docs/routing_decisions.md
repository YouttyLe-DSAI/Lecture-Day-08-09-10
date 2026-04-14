 Routing Decisions Log — Lab Day 09

**Nhóm:** 15  
**Ngày:** 2026-04-14

---

## Routing Decision #1 — Standard SLA Retrieval (q01)

**Task đầu vào:**
> "SLA xử lý ticket P1 là bao lâu?"

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `task contains SLA/ticket keywords: ['p1', 'sla', 'ticket']`  
**MCP tools được gọi:** Không  
**Workers called sequence:** `['retrieval_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- **Final Answer:** Trả lời dựa trên context retrieval (mặc dù trong trace repo hiện tại chunks=0 do môi trường, supervisor đã route đúng domain).
- **Confidence:** 0.1 (Base confidence khi không có context).
- **Correct routing?** **Yes** — Câu hỏi thuộc domain SLA/Ticket.

---

## Routing Decision #2 — Multi-hop Cross-domain (q13)

**Task đầu vào:**
> "Contractor cần Admin Access (Level 3) để khắc phục sự cố P1 đang active. Quy trình cấp quyền tạm thời như thế nào?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `multi-hop: task contains BOTH SLA and access control keywords → policy_tool_worker (will also retrieve) | risk_high flagged due to: ['tạm thời', 'contractor']`  
**MCP tools được gọi:** `search_kb`, `get_ticket_info`, `check_access_permission`  
**Workers called sequence:** `['retrieval_worker', 'policy_tool_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- **Risk High:** `True` (Do chứa từ khóa 'contractor' và 'tạm thời').
- **MCP usage:** Gọi tool `check_access_permission` với level=3. Trả về: "Level 3 KHÔNG có emergency bypass".
- **Correct routing?** **Yes** — Supervisor detect được cả nhu cầu tra cứu SLA (P1) và check permission (Level 3).

---

## Routing Decision #3 — Multi-hop & Emergency Fix (q15)

**Task đầu vào:**
> "Ticket P1 lúc 2am. Cần cấp Level 2 access tạm thời cho contractor để thực hiện emergency fix. Đồng thời cần notify stakeholders theo SLA."

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `multi-hop: task contains BOTH SLA and access control keywords → policy_tool_worker (will also retrieve) | risk_high flagged due to: ['emergency', '2am', 'tạm thời', 'contractor']`  
**MCP tools được gọi:** `search_kb`, `get_ticket_info`, `check_access_permission`

**Kết quả thực tế:**
- **Risk High:** `True`.
- **MCP Result:** Tool `check_access_permission` trả về `emergency_override: true` cho Level 2.
- **Correct routing?** **Yes** — Đây là trường hợp phức tạp nhất, yêu cầu phối hợp thông tin từ `access_control_sop.txt` và `sla_p1_2026.txt`.

---

## Routing Decision #4 — Default/Abstain Case (q09)

**Task đầu vào:**
> "ERR-403-AUTH là lỗi gì và cách xử lý?"

**Worker được chọn:** `retrieval_worker`  
**Route reason:** `no specific domain keyword matched → default retrieval`

**Nhận xét:** 
Supervisor không tìm thấy keyword thuộc domain SLA, Policy hay Access nên mặc định route về `retrieval_worker`. Đây là hành động an toàn ("fail-safe") để xem hệ thống có tài liệu kỹ thuật về mã lỗi này không. Tuy nhiên, vì không có chunk nào liên quan, `synthesis_worker` đã trả về "Không đủ thông tin".

---

## Tổng kết Routing Performance

### Routing Distribution (15 câu test)

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| `retrieval_worker` | 8 | 53% |
| `policy_tool_worker` | 7 | 46% |
| `human_review` | 0 | 0% |

### Routing Accuracy

- **Câu route đúng:** 15 / 15 (Tất cả domains đều được nhận diện chính xác qua bộ keyword rules).
- **Câu trigger Risk High:** 2 (q13, q15). Tuy nhiên, do supervisor ưu tiên multi-hop logic nên route sang `policy_tool_worker` thay vì `human_review` (chỉ trigger human review nếu có mã lỗi lạ đi kèm risk).

### Bài học rút ra (Lesson Learned)
1. **Keyword-based Routing:** Rất nhanh (<10ms) và chính xác cho các task có domain rõ ràng.
2. **Multi-hop Detection:** Việc đặt rule `has_sla and has_access` lên đầu giúp giải quyết các câu hỏi phức tạp mà single-agent Day 08 thường bỏ sót metadata.
3. **Risk Scoring:** Việc gán nhãn `risk_high` ngay tại supervisor giúp các worker phía sau (synthesis) có thể điều chỉnh giọng văn hoặc thêm cảnh báo cho người dùng.