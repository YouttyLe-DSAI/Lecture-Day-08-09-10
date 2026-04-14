# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Tuấn  
**Vai trò trong nhóm:** Trace & Docs Owner  
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

**Module/file tôi chịu trách nhiệm:**
- File chính: `eval_trace.py`
- Functions tôi implement: `run_test_questions()`, `run_grading_questions()`, `analyze_traces()`, `compare_single_vs_multi()`, `save_eval_report()`, `print_metrics()`
- Docs tôi chịu trách nhiệm: `docs/system_architecture.md`, `docs/routing_decisions.md`, `docs/single_vs_multi_comparison.md`, `reports/group_report.md`

Tôi chịu trách nhiệm Sprint 4 — chạy pipeline với 15 test questions, thu thập trace files, phân tích metrics, so sánh single vs multi-agent, và hoàn thiện tất cả documentation. `eval_trace.py` có CLI interface (`--grading`, `--analyze`, `--compare`) cho các modes khác nhau. `analyze_traces()` đọc tất cả JSON trace files và tính: routing_distribution, avg_confidence, avg_latency, mcp_usage_rate, hitl_rate, top_sources.

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Tôi import `run_graph()` và `save_trace()` từ graph.py (Cao). Trace format phụ thuộc vào AgentState schema (Cao) và worker IO logs (Ly). MCP tool calls (Nam) được reflect trong `mcp_tools_used` field.

**Bằng chứng:** eval_trace.py có đầy đủ CLI commands + đã chạy thành công 15/15 test questions.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Tách eval_trace.py thành 4 modes (default/run, --grading, --analyze, --compare) thay vì 1 script monolithic.

**Lý do:**

Ban đầu eval_trace.py chỉ có 1 main function chạy tất cả. Vấn đề: khi grading_questions.json chưa public (trước 17:00), không thể chạy script. Khi chỉ cần analyze traces đã có, phải chạy lại toàn bộ pipeline (mất ~90s cho 15 câu).

Tôi tách thành 4 modes:
- Default: chạy test questions + analyze + compare (full pipeline)
- `--grading`: chỉ chạy grading questions → JSONL log
- `--analyze`: chỉ đọc traces có sẵn → metrics
- `--compare`: chỉ generate comparison report

**Trade-off đã chấp nhận:**

Cần argparse setup (~10 dòng code thêm), nhưng tiết kiệm thời gian khi iterate: analyze traces mà không phải re-run pipeline.

**Bằng chứng từ trace/code:**

```bash
# Chạy full pipeline (15 câu, ~90s)
python eval_trace.py

# Chỉ analyze traces có sẵn (instant)
python eval_trace.py --analyze
# Output: avg_confidence: 0.605, avg_latency_ms: 7390, routing: 50/50

# Chỉ compare (instant)
python eval_trace.py --compare
# Output: eval_report.json
```

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** `mcp_tools_used` trong grading JSONL log ghi toàn bộ MCP tool objects (bao gồm output data lớn) thay vì chỉ tool names, làm JSONL file rất lớn và khó đọc.

**Symptom:** `artifacts/grading_run.jsonl` mỗi dòng dài 5000+ characters vì `mcp_tools_used` chứa full MCP response (chunks, ticket data, access rules...).

**Root cause:** Dòng 128 eval_trace.py: `"mcp_tools_used": result.get("mcp_tools_used", [])` copy toàn bộ MCP objects vào JSONL thay vì chỉ extract tool names.

**Cách sửa:** Thay bằng list comprehension: `"mcp_tools_used": [t.get("tool") for t in result.get("mcp_tools_used", [])]` — chỉ lấy tool name string.

**Bằng chứng trước/sau:**

Trước: `"mcp_tools_used": [{"tool": "check_access_permission", "input": {...}, "output": {"can_grant": true, "required_approvers": [...], ...}, "timestamp": "..."}]`  
Sau: `"mcp_tools_used": ["check_access_permission"]` — clean, compact, đúng format SCORING.md yêu cầu

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**

Documentation quality — cả 3 docs templates đều được điền với số liệu thực từ trace (không ước đoán). Routing decisions log có 4 entries với trace evidence cụ thể. Comparison doc có metrics table đầy đủ.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Chưa implement Day 08 baseline comparison (ghi N/A cho hầu hết Day 08 metrics). Nếu có thêm thời gian, sẽ chạy Day 08 eval.py để có delta thực tế.

**Nhóm phụ thuộc vào tôi ở đâu?**

Grading run log (artifacts/grading_run.jsonl) — nếu eval_trace.py crash, nhóm không có log chấm điểm. Documentation cũng chiếm 10 điểm nhóm.

**Phần tôi phụ thuộc vào thành viên khác:**

`run_graph()` từ Cao — toàn bộ pipeline phải chạy được trước khi tôi eval. Trace format phụ thuộc workers output (Ly) và MCP (Nam).

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ implement **automated accuracy scoring** trong eval_trace.py — so sánh `final_answer` với `expected_answer` từ test_questions.json bằng string matching + LLM-as-Judge. Trace q12 cho thấy confidence=0.30 nhưng tôi không tự động biết answer đúng hay sai — cần automated check thay vì manual review.

---

*Lưu file này với tên: `reports/individual/tuan.md`*
