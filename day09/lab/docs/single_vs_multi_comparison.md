# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** 15
**Ngày:** 2026-04-14

> So sánh Day 08 (single-agent RAG) với Day 09 (supervisor-worker).
> Số liệu Day 09 từ trace thật. Day 08 dựa trên baseline report ngày 13/04.

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | 0.83 | 0.394 | -0.436 | Giảm do model khống chế hallucination & filter context |
| Avg latency (ms) | 2035 | 4475 | +2,440 | Tăng do Supervisor routing & worker chaining |
| Abstain rate (%) | 27% | ~0% | -27% | Giảm mạnh nhờ Multi-agent xử lý được policy/exceptions |
| Multi-hop accuracy | 0% | Cao | +N/A | Cải thiện mạnh nhờ tool calling & cross-doc retrieval |
| Routing visibility | ✗ Không có | ✓ Có route_reason | N/A | Trace rõ ràng cho từng bước supervisor |
| Debug time (estimate) | ~15 phút | ~3 phút | -12 phút | Nhờ graph logging + worker isolation |
| MCP usage rate | 0% | 46% | +46% | 7/15 câu sử dụng external MCP tools |

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Cao (~83%) | Cao — retrieve đúng source cho q01, q02, q04, q05 |
| Latency | ~2,000ms | ~4,475ms (Avg total) |
| Observation | Một prompt duy nhất, không trace | 2 workers, trace rõ ràng per-step |

**Kết luận:** Multi-agent tăng latency do overhead của supervisor routing + worker IO logging nhưng bù lại cung cấp khả năng quan sát (observability) tuyệt vời.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | 0% | 2/2 multi-hop đúng (q13, q15) |
| Routing visible? | ✗ | ✓ — trace ghi rõ "multi-hop detected" |
| Observation | Khó biết pipeline dùng info từ doc nào | Sources: ['access_control_sop.txt', 'sla_p1_2026.txt'] rõ ràng |

**Kết luận:** Multi-agent rõ ràng tốt hơn cho multi-hop. Supervisor detect được overlap keywords → gọi retrieval + policy + MCP check_access_permission. Trace ghi 2 workers + 2 MCP tools cho q15.

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | 27% | 0% |
| Hallucination cases | N/A | 0 (context-based fallback không bịa) |
| Observation | Có thể hallucinate nếu retriever sai | Confidence thấp (0.41) signal rõ cần kiểm tra |

**Kết luận:** Multi-agent có confidence score giúp detect câu cần abstain. q09 (ERR-403-AUTH) confidence = 0.41 — thấp nhất trong 15 câu, signal đúng rằng answer không đáng tin.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: 15 phút
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic (keywords/rules)
  → Nếu retrieval sai → test retrieval_worker độc lập: python workers/retrieval.py
  → Nếu policy sai → test policy_tool_worker độc lập: python workers/policy_tool.py
  → Nếu synthesis sai → kiểm tra context_text và confidence
Thời gian ước tính: 3 phút
```

**Câu cụ thể nhóm đã debug:**

Câu q08 ("Quy trình xử lý sự cố P1 gồm mấy bước") — trace cho thấy retrieval trả về chunks từ `policy_refund_v4.txt` thay vì `sla_p1_2026.txt`. Root cause: embedding model rank refund doc cao hơn vì "quy trình" là keyword chung. Fix: tăng top_k hoặc thêm keyword match để boost SLA docs khi task chứa "P1".

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa retrieval_worker độc lập |
| A/B test một phần | Khó — phải clone toàn pipeline | Dễ — swap worker |

**Nhận xét:**

Multi-agent dễ extend hơn rõ ràng. Trong lab, nhóm đã thêm `check_access_permission` MCP tool mà không cần sửa retrieval hay synthesis. Chỉ cần: (1) thêm tool implement trong mcp_server.py, (2) thêm call trong policy_tool.py, (3) thêm route rule trong supervisor. Tổng: ~15 dòng code thay đổi.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 LLM call | 1 embedding + 1 LLM call (hoặc context-based) |
| Complex query | 1 LLM call | 1 embedding + 1-2 MCP calls + 1 LLM call |
| MCP tool call | N/A | ~5ms per tool (in-process mock) |

**Nhận xét về cost-benefit:**

Multi-agent tốn thêm ~2.4s latency so với single agent (do supervisor routing + worker chaining + MCP HTTP overhead). Tuy nhiên, benefit lớn nhất là khả năng xử lý các case phức tạp và trace visibility: khi answer sai, debug time giảm đáng kể.

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**

1. **Debuggability** — trace rõ ràng với route_reason, workers_called, mcp_tools_used giúp tìm bug nhanh gấp 5 lần.
2. **Multi-hop reasoning** — detect và xử lý được câu hỏi cross-document (SLA + Access Control) tốt hơn nhờ separate workers + MCP tools.

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. **Câu hỏi đơn giản** — latency tăng (~4.5s vs ~2s single-agent) mà accuracy không cải thiện vượt bậc. Overhead không đáng nếu chỉ làm FAQ chatbot tĩnh.

> **Khi nào KHÔNG nên dùng multi-agent?**

Khi toàn bộ câu hỏi là single-document, single-hop (VD: FAQ chatbot đơn giản). Chi phí setup + maintain nhiều workers + contracts không xứng đáng nếu pipeline đơn giản đã đủ tốt.

> **Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

1. LLM-based routing (thay keyword matching) để handle ambiguous queries
2. LLM-as-Judge confidence scoring thay vì heuristic
3. **ĐÃ HOÀN THÀNH**: Real MCP HTTP server (bonus +2) để decouple tools deployment.
4. Retry logic khi retrieval trả về low-quality chunks (confidence < 0.4 → re-query with expanded keywords)