# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Cao
**Vai trò trong nhóm:** MCP Owner  
**Ngày nộp:** 2026-04-14  

---

## 1. Tôi phụ trách phần nào?

**Module/file tôi chịu trách nhiệm:**
- File chính: `mcp_server.py`, phần MCP integration trong `workers/policy_tool.py`
- Functions tôi implement: `tool_search_kb()`, `tool_get_ticket_info()`, `tool_check_access_permission()`, `tool_create_ticket()`, `dispatch_tool()`, `list_tools()`, `_call_mcp_tool()` (trong policy_tool.py)

Tôi chịu trách nhiệm Sprint 3 — xây dựng MCP server và tích hợp MCP client vào policy_tool worker. MCP server expose 4 tools qua `dispatch_tool()` interface, mỗi tool có schema định nghĩa (TOOL_SCHEMAS) giống MCP protocol thật. `search_kb` kết nối ChromaDB qua retrieval worker. `get_ticket_info` trả về mock ticket data (P1-LATEST, IT-1234). `check_access_permission` kiểm tra access rules cho Level 1/2/3 với emergency bypass logic. `create_ticket` tạo mock ticket.

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`dispatch_tool()` được gọi từ `_call_mcp_tool()` trong policy_tool.py (Ly). MCP tool results được ghi vào `state["mcp_tools_used"]` — Tuấn trace format này trong eval_trace.py. TOOL_SCHEMAS match với contracts YAML.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Triển khai **Singleton Pattern** kết hợp Lazy Loading cho embedding function trong Retrieval Worker.

**Lý do:**

Trong quá trình tích hợp MCP tool `search_kb`, tôi nhận thấy mỗi lần tool được gọi, hệ thống lại mất hơn 20 giây để khởi tạo lại model SentenceTransformer hoặc kết nối OpenAI. Điều này làm cho MCP server phản hồi cực chậm, dẫn đến timeout ở phía client. 

Tôi quyết định thiết kế một cơ chế Singleton cho hàm `_get_embedding_fn()`. Model chỉ được load một lần duy nhất khi có request đầu tiên và được lưu vào cache (`_CACHED_EMBED_FN`). Các request sau đó sẽ dùng lại instance này ngay lập tức.

**Trade-off đã chấp nhận:**

Việc này làm cho request đầu tiên vẫn sẽ bị chậm (cold start), nhưng tổng thể latency của hệ thống giảm từ ~22s xuống còn <100ms cho các câu hỏi tiếp theo. Đây là sự đánh đổi cần thiết để đảm bảo tính ổn định của MCP HTTP server.

**Bằng chứng từ trace/code:**

```python
# workers/retrieval.py
_CACHED_EMBED_FN = None

def _get_embedding_fn():
    global _CACHED_EMBED_FN
    if _CACHED_EMBED_FN is not None:
        return _CACHED_EMBED_FN
    # ... logic load model ...
    return _CACHED_EMBED_FN
```

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** **Dimension Mismatch (1536 vs 384)** khi chạy MCP HTTP Server.

**Symptom:** Khi gọi tool `search_kb` qua HTTP, server trả về lỗi: `ChromaDB query failed: Collection expecting embedding with dimension of 1536, got 384`.

**Root cause:** Lỗi nằm ở việc quản lý biến môi trường. MCP Server chạy như một process FastAPI độc lập. Ban đầu, tôi quên không gọi `load_dotenv()` ở ngay đầu entry point của server. Kết quả là server không đọc được `OPENAI_API_KEY`, dẫn đến việc fallback sang model local (384 dim) thay vì dùng OpenAI (1536 dim) như dữ liệu đã index trong DB.

**Cách sửa:** 
1. Thêm `load_dotenv()` lên dòng đầu tiên của `mcp_host.py` và `retrieval.py`.
2. Chỉnh sửa logic `_get_embedding_fn()` để ưu tiên OpenAI nếu có key, và in log rõ ràng (🚀 [Retrieval] Using OpenAI) để debug dễ dàng hơn.

**Bằng chứng trước/sau:**

Trước: Server báo lỗi dimension mismatch và in log "BertModel LOAD REPORT" lặp lại.  
Sau: Server log in rõ: `🚀 [Retrieval] Using OpenAI Embeddings` và kết quả search trả về chính xác 1536 dimensions.

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**

Thiết kế kiến trúc **decoupled** cho MCP. Việc tách tool logic ra khỏi worker core giúp hệ thống cực kỳ dễ mở rộng. Tôi tự hào nhất là đã nâng cấp thành công lên **Real MCP HTTP Server** (Bonus +2), giúp nhóm có một giải pháp chuyên nghiệp hơn thay vì chỉ dùng mock class đơn giản.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Khả năng error handling ở giai đoạn đầu còn sơ sài, dẫn đến việc để lọt lỗi dimension mismatch làm gián đoạn buổi test. Tôi cần chú ý hơn đến việc đồng bộ môi trường giữa các process khác nhau.

**Nhóm phụ thuộc vào tôi ở đâu?**

Toàn bộ các câu hỏi phức tạp về Policy và Access Control (q13, q15) đều phụ thuộc vào "xương sống" MCP mà tôi xây dựng. Nếu MCP server sập, hệ thống sẽ mất khả năng kiểm tra quyền hạn thực tế.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ xây dựng một **Dashboard quản lý MCP** bằng FastAPI Swagger UI, cho phép giảng viên hoặc các thành viên khác có thể test từng tool một cách trực quan qua giao diện web mà không cần chạy code script. Điều này sẽ nâng tầm tính chuyên nghiệp của hệ thống trợ lý nội bộ.

---
