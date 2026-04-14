# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Lê Minh Tuấn
**Vai trò trong nhóm:** Trace & Docs Owner  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Trong buổi Lab Day 09, tôi đảm nhận vai trò là **Trace & Docs Owner**. Trách nhiệm chính của tôi tập trung vào Sprint 4: Xây dựng và hoàn thiện pipeline đánh giá hiệu năng hệ thống.

**Module/file tôi chịu trách nhiệm:**
- File chính: `eval_trace.py`
- Functions tôi implement: `analyze_traces()`, `compare_single_vs_multi()`, và cơ chế xuất báo cáo gộp `test_traces_combined.json`.

**Cách công việc của tôi kết nối với phần của thành viên khác:**
 Sau khi các bạn phụ trách S1 và Workers (S2, S3) hoàn thành logic chạy, tôi sử dụng file `eval_trace.py` để toàn bộ 15 câu hỏi của hệ thống. Tôi thu thập dữ liệu về độ trễ (latency), độ tự tin (confidence) và log routing từ Supervisor để tạo ra báo cáo so sánh với hệ thống Single-agent của Day 08. 

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**
- Commit: `d91a76b8` - "hoàn thiện: Xây dựng toàn bộ hệ thống Multi-Agent AI Helpdesk & Trace Eval (Sprint 1 - 4)".
- Code trong `eval_trace.py` tại phần phân tích Baseline Day 08.
## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)
**Quyết định:** Triển khai cơ chế lưu trữ "Double-Tracking Trace" 

Trong quá trình thực hiện Sprint 4, tôi đã quyết định không chỉ lưu các file JSON riêng lẻ cho từng lần chạy (`artifacts/traces/run_*.json`) mà còn tự động ghi đè và cập nhật một file tổng hợp duy nhất mang tên `test_traces_combined.json` mỗi khi pipeline đánh giá hoàn tất.

**Lý do:**
Ban đầu, hệ thống chỉ lưu các file lẻ. Điều này gây khó khăn cực lớn cho việc phân tích tổng quát. Nếu muốn biết trung bình thời gian phản hồi của 15 câu hỏi, tôi phải dùng vòng lặp đọc 15 file khác nhau, gây lãng phí tài nguyên IO. 
Các lựa chọn thay thế là chỉ dùng một file JSONL duy nhất , nhưng JSONL lại khó đọc bằng mắt thường. Vì vậy, tôi chọn giải pháp duy trì file lẻ để phục vụ kiểm tra chi tiết (khi cần soi kỹ 1 câu cụ thể) và file gộp để phục vụ phân tích metrics tổng hợp.

**Trade-off đã chấp nhận:**
Việc này sẽ tốn thêm một khoảng thời gian nhỏ (vài ms) ở cuối tiến trình để gộp dữ liệu, và chiếm thêm một chút dung lượng bộ nhớ. Tuy nhiên, so với lợi ích về mặt debug và báo cáo, sự đánh đổi này là hoàn toàn xứng đáng.

**Bằng chứng từ trace/code:**
Đoạn code tôi đã thêm vào cuối hàm `run_test_questions`:
```python
    # Save combined traces for easier reading
    combined_file = "artifacts/test_traces_combined.json"
    with open(combined_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** `UnicodeDecodeError` khi đọc trace trên môi trường Windows.

**Symptom (pipeline làm gì sai?):**
Khi tôi chạy lệnh `python eval_trace.py --analyze`, script lập tức văng lỗi và dừng hẳn: `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 31`. Không có báo cáo nào được tạo ra mặc dù các file trace đã có sẵn.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**
Lỗi nằm ở logic đọc file trong hàm `analyze_traces`. Python trên hệ điều hành Windows (tiếng Việt/English) thường mặc định sử dụng bảng mã `cp1252` hoặc `GBK` tùy locale. Trong khi đó, các câu trả lời của AI chứa rất nhiều ký tự tiếng Việt có dấu. Khi hàm `open()` được gọi mà không có tham số encoding, nó cố gắng giải mã các byte UTF-8 bằng bảng mã Window-1252, dẫn đến xung đột và crash.

**Cách sửa:**
Tôi đã rà soát toàn bộ file `eval_trace.py` và ép kiểu định dạng `encoding="utf-8"` cho tất cả các thao tác đọc (`r`) và ghi (`w`) file. Điều này đảm bảo tính nhất quán của dữ liệu tiếng Việt trên mọi môi trường chạy (Windows/Linux).

**Bằng chứng trước/sau:**
```python
# Trước:
with open(os.path.join(traces_dir, fname)) as f:
# Sau (Đã fix):
with open(os.path.join(traces_dir, fname), encoding="utf-8") as f:
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**
Tôi làm tốt nhất ở khâu **Dữ liệu và Đối chiếu**. Tôi không chỉ chạy code cho xong mà còn dành thời gian điền chính xác các thông số Baseline của Day 08 (2035ms latency, 27% abstain) để kết quả so sánh trong `eval_report.json` mang tính thuyết phục cao nhất.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Tôi còn hơi chậm trong việc xử lý các lỗi môi trường ban đầu. Việc loay hoay với lỗi `charmap` mất khoảng 15 phút đầu giờ khiến tiến độ tổng hợp report của nhóm bị chậm lại một chút so với kế hoạch.

**Nhóm phụ thuộc vào tôi ở đâu?**
Nếu tôi không xong phần `analyze_traces`, nhóm sẽ không có số liệu cụ thể để điền vào Dashboard và Slide thuyết trình. Các bạn làm Worker sẽ không biết con Bot của mình thực tế nhanh hay chậm hơn bản cũ bao nhiêu.

**Phần tôi phụ thuộc vào thành viên khác:**
Tôi phụ thuộc hoàn toàn vào output của `graph.py`. Nếu Supervisor định tuyến sai hoặc Worker crash, các file trace của tôi sẽ bị rỗng hoặc lỗi, dẫn đến việc phân tích metrics không thể thực hiện được.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Nếu có thêm 2 giờ, tôi sẽ phát triển một module **Auto-Grading đơn giản**. Hiện tại chúng ta so sánh định tính qua `analysis` text, nhưng tôi muốn dùng một con LLM làm "Judge" (Trọng tài) để so khớp `final_answer` với `expected_answer` trong file `test_questions.json`, từ đó đưa ra điểm số Accuracy (0-100%) một cách tự động thay vì phải đọc trace bằng mắt.

---
*Lưu file này với tên: `reports/individual/le_minh_tuan.md`*
