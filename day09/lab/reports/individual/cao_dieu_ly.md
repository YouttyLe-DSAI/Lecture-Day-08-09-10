# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Ly  
**Vai trò trong nhóm:** Worker Owner  
**Ngày nộp:** 2026-04-14  


---

## 1. Tôi phụ trách phần nào?

**Module/file tôi chịu trách nhiệm:**
- File chính: `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py`
- Functions tôi implement: `retrieve_dense()`, `run()` (retrieval), `analyze_policy()`, `run()` (policy_tool), `synthesize()`, `_call_llm()`, `_estimate_confidence()`, `run()` (synthesis)

Tôi chịu trách nhiệm toàn bộ Sprint 2 — implement 3 workers theo đúng contracts trong `worker_contracts.yaml`. Retrieval worker kết nối ChromaDB qua sentence-transformers (all-MiniLM-L6-v2), query top-3 chunks, và format output theo contract. Policy tool worker phân tích exceptions (Flash Sale, digital product, activated product) bằng rule-based logic. Synthesis worker gọi LLM (OpenAI/Gemini) hoặc dùng context-based fallback khi không có API key.

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Workers được gọi từ `graph.py` (Nam) qua `run()` interface. Policy tool worker gọi `dispatch_tool()` từ `mcp_server.py` (Cao). Output format khớp contracts YAML để Tuấn có thể trace đúng.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Implement context-based fallback trong `_call_llm()` thay vì trả error message khi không có API key.

**Lý do:**

Ban đầu, synthesis worker trả `"[SYNTHESIS ERROR] Không thể gọi LLM"` khi API key không set. Điều này làm toàn bộ pipeline vô dụng khi test offline. Tôi implement `_extract_answer_from_context()` — một hàm trích xuất trực tiếp từ chunks + policy_result, format câu trả lời có citation mà **không bao giờ hallucinate** (chỉ dùng text từ chunks).

Lựa chọn thay thế: hard-code mock answers, nhưng cách này không scale và không grounded.

**Trade-off đã chấp nhận:**

Answer quality từ fallback thấp hơn LLM (không paraphrase, không tổng hợp), nhưng đảm bảo: (1) pipeline luôn chạy được, (2) không hallucinate, (3) sources vẫn được cite.

**Bằng chứng từ trace/code:**

```python
# workers/synthesis.py — _extract_answer_from_context()
# Khi LLM API không có:
# - Chunks rỗng → "Không đủ thông tin trong tài liệu nội bộ"
# - Có chunks → format trực tiếp với [1], [2]... citation
# - Có policy exceptions → append ngoại lệ
# - Có access_check → append MCP result
```

Trace q06: `confidence=0.73, sources=['sla_p1_2026.txt']` — answer chứa đúng SLA P1 info từ context mà không cần LLM.

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** Policy tool worker chỉ gọi MCP `get_ticket_info` khi task có "ticket/p1/jira", nhưng KHÔNG gọi `check_access_permission` — thiếu access check cho câu multi-hop.

**Symptom:** Câu q13 ("Contractor cần Admin Access Level 3") trả lời phần policy refund thay vì access control. Access check results bị thiếu hoàn toàn trong answer.

**Root cause:** Step 3 trong `run()` chỉ có `get_ticket_info` call, không có logic detect access-related keywords để gọi `check_access_permission`.

**Cách sửa:** Thêm block detect access keywords trong task → gọi `_call_mcp_tool("check_access_permission", {...})` với auto-detect access_level (2 hoặc 3) và is_emergency flag. Merge kết quả vào `state["policy_result"]["access_check"]`.

**Bằng chứng trước/sau:**

Trước: q13 trace → `mcp_tools_used: []`, answer thiếu access info  
Sau: q13 trace → `mcp_tools_used: ["check_access_permission"]`, answer có đầy đủ "Level 3 cần 3 approvers: Line Manager + IT Admin + IT Security, KHÔNG có emergency bypass"

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**

Context-based fallback — giải quyết vấn đề pipeline crash khi không có API key. Confidence estimation function cũng giúp detect low-quality answers (q12: confidence=0.30 đúng phản ánh temporal scoping complexity).

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Policy analysis vẫn rule-based (keyword matching) — không dùng LLM để phân tích sâu. Một số edge cases (VD: "sản phẩm lỗi nhà sản xuất + Flash Sale" — hai conditions đối chọi) chưa xử lý tốt.

**Nhóm phụ thuộc vào tôi ở đâu?**

Toàn bộ worker `run()` functions — graph.py call trực tiếp. Nếu workers fail, pipeline không chạy được.

**Phần tôi phụ thuộc vào thành viên khác:**

`dispatch_tool()` từ Cao (MCP). AgentState schema từ Cao. ChromaDB index phải build trước khi retrieval hoạt động.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ upgrade `analyze_policy()` từ rule-based sang **LLM-based policy analysis**. Với việc bạn Cao đã hoàn thành MCP HTTP server tích hợp vào policy worker, bước tiếp theo hoàn hảo nhất là dùng LLM để phân tích logic policy phức tạp (temporal scoping v3 vs v4) để tăng độ chính xác thay vì chỉ dùng regex.

---
