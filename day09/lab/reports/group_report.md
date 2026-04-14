# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** 15  
**Thành viên:**
| Tên | Vai trò | Email | Trách nhiệm chính |
|-----|---------|-------|-------------------|
| Nam | Supervisor Owner | dauvannam321@gmail.com | graph.py, Routing Logic, Multi-hop detection |
| Ly | Worker Owner | caodieuly1508@gmail.com | Retrieval, Policy_tool, Synthesis workers |
| Cao | MCP Owner | tricao2003@gmai.com | MCP Server, Real HTTP Server (Bonus), optimization |
| Tuấn | Trace & Docs Owner | leminhtuan.ai.work@gmail.com | eval_trace.py, Metrics Analysis, Documentation |

**Ngày nộp:** 2026-04-14  

---

## 1. Kiến trúc nhóm đã xây dựng

**Hệ thống tổng quan:**

Nhóm đã refactor thành công pipeline RAG nguyên khối (Day 08) sang kiến trúc **Supervisor-Worker** linh hoạt. Hệ thống bao gồm:
1. **Supervisor Node**: Điều phối luồng dựa trên keyword matching nâng cao và multi-hop detection.
2. **Workers Layer**: Gồm 3 worker chuyên biệt (Retrieval, Policy Tool, Synthesis) giao tiếp qua Shared State.
3. **Real MCP HTTP Server (Bonus +2)**: Toàn bộ tools (`search_kb`, `check_access_permission`, v.v.) được đóng gói trong một FastAPI Server độc lập, giúp tách biệt hoàn toàn logic nghiệp vụ khỏi core orchestration.

**Điểm nhấn kỹ thuật:**
- **Singleton Optimization**: Chúng tôi triển khai Singleton Pattern cho embedding model. Thay vì load model 20s cho mỗi request, model chỉ khởi tạo một lần duy nhất, giúp giảm latency cực lớn cho các MCP tool calls.
- **Robust Exception Handling**: Policy worker có khả năng xử lý các trường hợp ngoại lệ (Flash Sale, Digital Products) thông qua việc kết hợp context từ retrieval và tool kết quả từ MCP.

---

## 2. Quyết định kỹ thuật quan trọng nhất

**Quyết định:** Triển khai **Multi-hop Routing Logic** dựa trên Keyword Overlap.

**Bối cảnh vấn đề:**
Các câu hỏi phức tạp (như q13, q15) yêu cầu thông tin đồng thời từ cả tài liệu SLA và tài liệu Access Control. Nếu chỉ sử dụng if/else đơn giản, Supervisor sẽ chỉ gửi request đến một worker duy nhất, dẫn đến câu trả lời bị thiếu hụt thông tin trầm trọng.

**Giải pháp:**
Chúng tôi thiết lập một rule ưu tiên cao nhất: Nếu task chứa cả từ khóa thuộc domain SLA (P1, ticket) **VÀ** Access (access, level, permission), hệ thống sẽ tự động định tuyến sang `policy_tool_worker` đồng thời kích hoạt cờ `needs_tool=True`. Worker này sau đó sẽ phối hợp gọi MCP tools và retrieval để bao phủ toàn bộ context.

**Kết quả:** 
Tỷ lệ xử lý đúng các câu hỏi Multi-hop đạt **100% (2/2)** trong bộ test, điều mà hệ thống Single-agent Day 08 hoàn toàn không làm được.

---

## 3. Kết quả grading questions

**Trạng thái:** Đã hoàn thành chạy 10/10 câu hỏi grading (`artifacts/grading_run.jsonl`).

**Tổng điểm raw ước tính:** **~90 / 96**

**Phân tích các câu tiêu biểu:**
- **gq07 (Abstain)**: Hệ thống đạt điểm tối đa nhờ cơ chế context-fallback. Khi không tìm thấy mức phạt cụ thể trong tài liệu, pipeline trả về "Không đủ thông tin" thay vì bịa đặt con số.
- **gq09 (Multi-hop hard)**: Trace ghi nhận việc gọi đồng thời 2 MCP tools và trích xuất dữ liệu từ 2 file tài liệu khác nhau (`access_control_sop.txt` và `sla_p1_2026.txt`).

---

## 4. So sánh Day 08 vs Day 09 — Phân tích chỉ số

Dựa trên dữ liệu thực tế từ `eval_report.json`:

| Metric | Day 08 (Single) | Day 09 (Multi-Agent) | Nhận xét |
|--------|----------------|----------------------|----------|
| **Avg Latency** | 2035ms | **4246ms** | Tăng ~2.2s do overhead routing & HTTP MCP calls, nhưng ổn định nhờ Singleton. |
| **Avg Confidence** | 0.83 | **0.397** | Thấp hơn do model kiểm soát hallucination chặt chẽ hơn (grounded truth). |
| **MCP Usage** | 0% | **46%** | Gần một nửa số câu hỏi yêu cầu can thiệp từ external tools. |
| **Abstain Rate** | 27% | **~0%** | Multi-agent xử lý được các case "khó" mà Single-agent bỏ qua. |

**Điều nhóm quan sát được:**
Multi-agent không chỉ là việc chia nhỏ code, mà là việc tạo ra **tính minh bạch (Observability)**. Với `route_reason` và `workers_called` trong trace, thời gian debug lỗi của nhóm giảm từ 15 phút xuống còn dưới 3 phút cho mỗi case.

---

## 5. Phân công và đánh giá nhóm

| Thành viên | Trách nhiệm thực tế | Đóng góp nổi bật |
|------------|-------------------|------------------|
| **Nam** | Supervisor & Graph | Thiết kế Multi-hop routing algorithm và risk-scoring logic. |
| **Ly** | Workers logic | Xây dựng cơ chế Synthesis fallback không cần API key (Zero-hallucination). |
| **Cao** | MCP & Optimization | Triển khai Real HTTP Server (FastAPI) và tối ưu Singleton Embedding. |
| **Tuấn** | Eval & Traces | Xây dựng pipeline tự động hóa việc tính toán metrics từ traces. |

**Đánh giá chung:**
Nhóm phối hợp cực kỳ tốt thông qua việc thống nhất **Worker Contracts (YAML)** ngay từ đầu. Điều này giúp các thành viên có thể code độc lập mà không bị dẫm chân lên nhau.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì?

1. **LLM-as-Judge**: Triển khai một worker chuyên chấm điểm output của các worker khác để tự động hóa khâu đánh giá chất lượng (Accuracy).
2. **Auto-Retry Logic**: Nếu confidence < 0.3, Supervisor sẽ tự động yêu cầu Retrieval mở rộng `top_k` hoặc thay đổi keyword để tìm kiếm lại.
3. **Decoupled Frontend**: Xây dựng một UI Dashboard để theo dõi graph chạy real-time qua websocket kết nối với MCP Server.

---