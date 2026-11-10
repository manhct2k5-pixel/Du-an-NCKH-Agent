# Giao diện trình diễn NCKH — phiên bản 1.3

Giao diện được tổ chức để giảng viên theo dõi phương pháp, xem hệ thống thực thi và đối chiếu bằng chứng thực nghiệm.

## Kịch bản trình bày

1. **Trang chủ:** giới thiệu bài toán, kiến trúc và kết quả holdout PaySim. Các metric tại đây là kết quả offline của model, không phải metric của vài giao dịch demo.
2. **Giao dịch:** chọn Thấp / Trung bình / Cao và bấm **Chạy giao dịch**. Các mẫu được nạp vào form chỉnh sửa được; XGBoost hiện tại chấm thật, không ép nhánh hoặc thay score trên UI. Định danh mới được tạo khi nạp mẫu để hạn chế phụ thuộc lịch sử của lần trình diễn trước.
3. **Kết quả:** theo dõi đầu vào → đặc trưng online → XGBoost + SHAP → điều tra nếu cần → quyết định. Các bước chỉ được đánh dấu sau khi API hoàn tất; nhánh low/high ghi rõ bỏ qua ReAct.
4. **Giám sát:** mở đúng giao dịch vừa gửi để xem SHAP, bằng chứng agent và anomaly sidecar. Điểm vận hành đã hiệu chỉnh được giải thích riêng với xác suất gốc.
5. **Xác minh:** với case review/step-up, dùng link **Xác minh giao dịch này** để đưa đúng case lên đầu danh sách, kể cả khi backlog cũ lớn. Ghi quyết định, ghi chú và nhãn thật khi đã biết. Chưa biết nhãn thì để trống; lưu quyết định không tự retrain model.
6. **Nghiên cứu:** trình bày số liệu final B8/B10/B11/B12; mở JSON đối chiếu khi cần. Baseline và các báo cáo trước đây nằm trong phần mở rộng để trả lời câu hỏi sâu hơn.

Có thể khởi động bằng `source .venv/bin/activate` rồi `python run_fraud_flow.py serve`. Chờ service khởi động xong và mở trang Giao dịch trước buổi trình bày. Các giao dịch gửi khi chạy bình thường vẫn được ghi vào log của phiên chạy; kiểm thử phát triển dùng bản sao tạm riêng.

## Các ranh giới cần nói rõ

- Ba nhánh mẫu là kịch bản minh họa dự kiến. Đổi dữ liệu, model hoặc lịch sử online có thể đổi nhánh thực tế.
- Trong phép thử, model active tạo low → approve, medium → agent/review và high → block. Đây là kiểm tra luồng, không thay cho đánh giá thống kê trên holdout.
- Mặc định dùng agent **heuristic local**, không gọi LLM ngoài. Chế độ `serve --llm-api` hỗ trợ DeepSeek/OpenAI. Khối **Agent có thực sự chạy?** trình bày bằng chứng từng giao dịch; `/llm/status` tách cấu hình với phản hồi quan sát được. Lần thử DeepSeek thật trả HTTP 402 vì thiếu số dư; chưa nhận phản hồi model. [Cách đối chiếu và cấu hình](LLM_RUNTIME.md).
- B8 medium là deterministic offline replay; không phải phép đo toàn bộ ReAct runtime.
- B10 là bootstrap của model cố định trên test, không đại diện toàn bộ bất định huấn luyện.
- B11 local latency loại Redis, network, external LLM/API và logging. Thời gian hiển thị ở giao dịch demo là phép đo khác.
- B12 frozen/transfer/native là ba thiết lập khác nhau; chưa có cơ sở kết luận model PaySim tổng quát hóa tốt trực tiếp sang IEEE-CIS.

## Các sửa đổi UI/UX

- Nút chạy có trạng thái đang xử lý; chặn bấm lặp, khóa reset/chuyển mẫu khi đang gửi.
- Kiểm tra số âm/rỗng trên form, hiển thị lỗi tại trường, đọc được lỗi validation 422 và timestamp 400; lỗi kết nối giữ nguyên đầu vào.
- Tự chuyển focus và cuộn tới kết quả; có thông báo trạng thái cho trình đọc màn hình.
- Form được đưa lên sớm, JSON và định danh đặt trong phần mở rộng. Thời điểm bắt đầu form trên mobile 390 px giảm từ khoảng 2222 px còn khoảng 661 px.
- Điều hướng tiếng Việt; link từ thẻ giao dịch tới bằng chứng; giữ case đang xem khi tăng số mục trong hàng đợi.
- Tooltip hỗ trợ focus/cảm ứng/Escape và nằm trong viewport; vùng cuộn có khả năng truy cập bằng bàn phím.
- Sửa tràn ngang từ tooltip và intrinsic size của CSS grid; không che toàn trang bằng `overflow-x:hidden`.

## Kiểm chứng

- **63 kiểm thử Python đạt**, gồm đọc đúng artifact final, giữ case đang trình diễn trong danh sách review giới hạn, đếm thực thi heuristic, parse chat message, sửa JSON, fallback review, SDK OpenAI/DeepSeek qua HTTP mô phỏng và xử lý lỗi API.
- Chromium thật, API thật và Redis riêng: ba kịch bản đi đúng ba nhánh; đã lưu xác minh và kiểm tra case rời hàng đợi.
- Kiểm tra gửi lặp trong mạng chậm mô phỏng, lỗi form, phản hồi 422, timestamp sai và lỗi kết nối.
- Sáu màn hình ở 1440, 390 và 320 px: không tràn ngang; không ghi nhận `pageerror`; không phát hiện vi phạm trong bộ quy tắc axe WCAG A/AA đã chọn. Bảng lịch sử mở rộng và tooltip bàn phím được kiểm tra thêm. Đây không phải chứng nhận accessibility.
- Model, artifact thực nghiệm và log production giữ nguyên; không chạy lại benchmark final để tạo số liệu mới cho UI.

[Kết quả kiểm tra trình duyệt](ui-audit/nckh/results.json) · [Trang chủ](ui-audit/nckh/desktop-home.png) · [Trình diễn medium](ui-audit/nckh/desktop-demo-result.png) · [Bằng chứng thực nghiệm](ui-audit/nckh/desktop-research.png) · [Mobile](ui-audit/nckh/mobile-form.png).

Đợt bổ sung kiểm chứng LLM: [kết quả runtime thực tế và kiểm tra phần bằng chứng mở rộng](ui-audit/nckh/llm-runtime-results.json). Nhãn backend API và log cũ được kiểm tra thêm bằng phản hồi mô phỏng, ghi riêng trong JSON; không có cuộc gọi LLM ngoài.

Cập nhật 10/11/2026: [DeepSeek Web qua DS2API đã chạy thật](DS2API_SETUP.md), mẫu medium có 4 công cụ và 6 phản hồi model qua API, 0 lỗi parser. 68 kiểm thử Python đạt; các kết quả offline trước đây giữ nguyên.
