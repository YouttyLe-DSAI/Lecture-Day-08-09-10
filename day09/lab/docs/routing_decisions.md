# Routing Decisions Log — Lab Day 09

**Nhóm:** Cao - Ly - Nam - Tuấn  
**Ngày:** 2026-04-14

> **Hướng dẫn:** Ghi lại ít nhất **3 quyết định routing** thực tế từ trace của nhóm.
> Mỗi entry có: task đầu vào → worker được chọn → route_reason → kết quả thực tế.

---

## Routing Decision #1 — SLA Retrieval

**Task đầu vào:**
> "Ticket P1 được tạo lúc 22:47. Ai sẽ nhận thông báo đầu tiên và qua kênh nào? Escalation xảy ra lúc mấy giờ?"

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `task contains SLA/ticket keywords: ['p1', 'ticket', 'escalation']`  
**MCP tools được gọi:** Không  
**Workers called sequence:** `['retrieval_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- final_answer (ngắn): Trích dẫn từ sla_p1_2026.txt — phản hồi 15 phút, escalation 10 phút, Slack #incident-p1 + email + PagerDuty
- confidence: 0.68
- Correct routing? Yes — câu chỉ cần retrieve SLA doc

**Nhận xét:** Routing đúng. Task chứa rõ ràng keywords P1/ticket/escalation nên supervisor route sang retrieval_worker. Không cần policy check vì đây là câu hỏi factual về SLA quy trình.

---

## Routing Decision #2 — Policy Exception Detection

**Task đầu vào:**
> "Khách hàng đặt đơn ngày 31/01/2026 và yêu cầu hoàn tiền ngày 07/02/2026. Sản phẩm lỗi nhà sản xuất, chưa kích hoạt, không phải Flash Sale. Được hoàn tiền không?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains policy/refund keywords: ['hoàn tiền', 'flash sale']`  
**MCP tools được gọi:** Không (policy được check bằng rule-based trong worker)  
**Workers called sequence:** `['retrieval_worker', 'policy_tool_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- final_answer (ngắn): Đơn đặt trước 01/02/2026 áp dụng chính sách v3, không phải v4. Cần xác nhận với CS Team.
- confidence: 0.30
- Correct routing? Yes — câu cần kiểm tra policy + temporal scoping

**Nhận xét:** Routing đúng và confidence thấp (0.30) phản ánh đúng reality — đây là câu temporal scoping phức tạp, tài liệu chỉ có v4 nhưng đơn hàng thuộc v3. Policy worker detect được note version phù hợp.

---

## Routing Decision #3 — Multi-hop Cross-document

**Task đầu vào:**
> "Ticket P1 lúc 2am. Cần cấp Level 2 access tạm thời cho contractor để thực hiện emergency fix. Đồng thời cần notify stakeholders theo SLA. Nêu đủ cả hai quy trình."

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `multi-hop: task contains BOTH SLA and access control keywords → policy_tool_worker (will also retrieve) | risk_high flagged due to: ['2am', 'tạm thời', 'contractor']`  
**MCP tools được gọi:** `get_ticket_info`, `check_access_permission`  
**Workers called sequence:** `['retrieval_worker', 'policy_tool_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- final_answer (ngắn): Nêu 2 quy trình song song: (1) SLA P1 notifications — Slack, email, PagerDuty, escalation 10 phút. (2) Level 2 access — CÓ emergency bypass, cần Line Manager + IT Admin on-call.
- confidence: 0.68
- Correct routing? Yes — multi-hop detection hoạt động, gọi 2 MCP tools

**Nhận xét:** Đây là routing phức tạp nhất. Supervisor detect multi-hop (SLA + access keywords cùng lúc) → route sang policy_tool_worker + retrieval. MCP check_access_permission(level=2, emergency=True) trả về đúng emergency bypass rule. Sources: ['access_control_sop.txt', 'sla_p1_2026.txt'].

---

## Routing Decision #4 — Abstain case

**Task đầu vào:**
> "ERR-403-AUTH là lỗi gì và cách xử lý?"

**Worker được chọn:** `retrieval_worker`  
**Route reason:** `no specific domain keyword matched → default retrieval`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**

Câu này không chứa keyword nào trong bộ routing rules (không có P1, SLA, hoàn tiền, access...). ERR-403-AUTH cũng không match pattern "err-\d{3}" vì chứa thêm "-AUTH". Supervisor route default sang retrieval_worker — đúng vì cần thử retrieve trước. ChromaDB trả về chunks không liên quan, confidence thấp (0.41). Nếu có LLM, synthesis sẽ abstain đúng. Lý tưởng nhất: supervisor nên detect unknown error code → human_review. Cần cải thiện regex pattern.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 8 | 53% |
| policy_tool_worker | 7 | 47% |
| human_review | 0 | 0% |

### Routing Accuracy

> Trong 15 câu test, bao nhiêu câu supervisor route đúng?

- Câu route đúng: 13 / 15
- Câu route sai (đã sửa bằng cách nào?): q09 (ERR-403-AUTH) nên route sang human_review thay vì retrieval; q08 (quy trình P1) retrieval đúng nhưng retrieve sai doc
- Câu trigger HITL: 0

### Lesson Learned về Routing

> Quyết định kỹ thuật quan trọng nhất nhóm đưa ra về routing logic là gì?

1. **Dùng keyword matching thay vì LLM classifier** — nhanh hơn (~5ms vs ~800ms cho mỗi LLM call), đủ chính xác cho 5 categories của lab. Trade-off: không handle được câu hỏi ambiguous.
2. **Multi-hop detection** — khi task chứa BOTH SLA + access keywords, supervisor route sang policy_tool_worker và gọi thêm retrieval + MCP. Đây là quyết định quan trọng nhất giúp q13 và q15 trả lời đúng.

### Route Reason Quality

> Nhìn lại các `route_reason` trong trace — chúng có đủ thông tin để debug không?

Route reason hiện tại format rõ ràng: liệt kê keywords matched, flag risk khi có, và note multi-hop khi detect. Ví dụ: `"task contains SLA/ticket keywords: ['p1', 'sla', 'ticket']"` — đủ để debug nhanh tại sao route như vậy. Cải tiến: thêm confidence score cho routing decision thay vì chỉ binary match.
