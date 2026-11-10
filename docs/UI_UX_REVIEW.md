# Kiểm tra UI/UX — 2026-11-09

> Đây là báo cáo trước khi sửa UI. Các lỗi luồng gửi, xác minh, responsive và bàn phím đã được xử lý trong bản 1.3; xem [giao diện trình diễn NCKH và kiểm chứng sau sửa](DEMO_NCKH.md).

Đã mở Chromium thật, thao tác form, gửi request tới API/Redis thật trong bản sao tạm, chụp màn hình và chạy axe-core. Phạm vi: trang chủ, nhập giao dịch, dashboard, review queue, docs và research ở 1440×1000, 390×844 và 320×740. Luồng submit được thử thêm với mạng chậm mô phỏng để kiểm tra phản hồi và gửi lặp.

**Kết luận:** giao diện có màu sắc, kiểu chữ và thẻ nội dung nhất quán, nhưng luồng nhập giao dịch và xử lý review còn các vấn đề ảnh hưởng sử dụng. Đây là báo cáo kiểm tra; chưa thay đổi mã giao diện trong đợt này.

## Cần ưu tiên sửa

### 1. P1 — Có thể gửi trùng giao dịch khi bấm nhiều lần

Trong lúc request đang chờ, nút vẫn có chữ “Gửi giao dịch”, `disabled=false`, form không có `aria-busy`. Bấm hai lần tạo **hai POST** thực sự. Backend tự tạo ID mới cho mỗi request nên hai lần gửi được xử lý như hai giao dịch.

Nguồn: [transaction_form.js:224](../fraud_flow/static/js/transaction_form.js#L224). Cần có trạng thái đang xử lý, khóa submit và reset trong lúc chờ, khôi phục trong `finally`; giữ nguyên dữ liệu khi lỗi.

### 2. P1 — Lỗi nhập liệu không cho biết người dùng cần sửa gì

Điền số tiền `-1` rồi gửi: API trả 422 đúng, nhưng UI hiện **`[object Object]`** vì chuyển mảng `detail` của FastAPI trực tiếp thành `Error`. Input cũng chưa có `min="0"` hoặc thông báo lỗi gắn với trường.

Nguồn: [transaction_form.js:240](../fraud_flow/static/js/transaction_form.js#L240), [transaction_form.html:63](../fraud_flow/templates/transaction_form.html#L63). Cần đọc từng `loc`/`msg`, dịch thông báo dễ hiểu và đưa focus về trường sai. Trường bắt buộc nên có ràng buộc HTML phù hợp với API.

### 3. P1 — Review queue chưa có thao tác hoàn tất review trên giao diện

Trang có các case pending nhưng **không có form hoặc nút duyệt/chặn**; mỗi thẻ chỉ có “Mở trên dashboard” và “JSON”. Backend có API review, nhưng người phân tích phải chuyển sang Swagger hoặc công cụ gửi request để hoàn thành công việc.

Nguồn: [review_queue.html:77](../fraud_flow/templates/review_queue.html#L77). Cần thêm thao tác approve/block/review, ghi chú analyst, xác nhận quyết định và cập nhật hàng đợi sau khi lưu thành công. Không tự gán nhãn gian lận khi chỉ thay đổi quyết định vận hành.

### 4. P1 — Dashboard tràn ngang trên desktop và mobile

| Chiều rộng viewport | Chiều rộng tài liệu |
|---:|---:|
| 1440 px | 1496 px |
| 390 px | 471 px |
| 320 px | 424 px |

Đã xác nhận tooltip metric là một nguyên nhân: tạm ẩn pseudo-element tooltip trong trình duyệt làm desktop hết tràn (1496 → 1440 px). Mobile vẫn còn tràn 397/390 px và 351/320 px sau bước đó, nên còn cần xử lý kích thước nội dung responsive.

Nguồn: [dashboard.css:808](../fraud_flow/static/css/dashboard.css#L808), các lưới metric và breakpoint mobile. Cần giới hạn vị trí/kích thước tooltip theo viewport và chỉnh các cột nhỏ; không chỉ che lỗi bằng `overflow-x:hidden` trên body.

## Nên sửa tiếp

### 5. P2 — Người dùng mobile khó thấy form và kết quả

Ở 390 px, form bắt đầu cách đầu trang khoảng **2222 px**: header, hero, status và demo notes chiếm nhiều màn hình trước thao tác chính. Sau submit, đầu phần kết quả còn nằm **1493 px dưới vị trí viewport hiện tại** trong khi màn hình cao 844 px. Không có cuộn tới kết quả, chuyển focus hoặc live region báo đã xong.

Nguồn: [transaction_form.html](../fraud_flow/templates/transaction_form.html), [transaction_form.js:154](../fraud_flow/static/js/transaction_form.js#L154). Nên đưa form lên sớm trên mobile, thu gọn JSON/ghi chú vào vùng mở rộng, đặt phản hồi gần nút gửi và thông báo kết quả bằng status/live region phù hợp.

### 6. P2 — Có vùng cuộn không sử dụng được bằng bàn phím

axe-core phát hiện `scrollable-region-focusable` mức serious trên mobile:

- Dashboard: `.case-list`, `.queue-list`, `.trace-list`; thêm `.sim-confusion-grid` ở 320 px.
- Docs: `.table-shell`; thêm các `.confusion-wrap` ở 320 px.
- Research: bốn `.table-wrap`.

Nguồn: [dashboard.html](../fraud_flow/templates/dashboard.html), [docs_portal.html](../fraud_flow/templates/docs_portal.html), [research.html:49](../fraud_flow/templates/research.html#L49). Cần khả năng focus có chủ đích, tên vùng và focus indicator; kiểm tra cuộn bằng phím mũi tên. Các tooltip `?` cũng cần cơ chế truy cập bằng bàn phím và cảm ứng, hiện phần lớn là span chỉ phục vụ hover.

### 7. P2 — Các thẻ case trên dashboard không dẫn tới case

Các mục Recent Cases và queue card được render bằng `<article>`, không có link hoặc nút mở chi tiết. Người dùng có thể thấy ID nhưng phải sang trang review khác để tìm link. Nút “Xem thêm case” cũng không giữ `tx_id` đang xem.

Nguồn: [dashboard.html:44](../fraud_flow/templates/dashboard.html#L44), [dashboard.html:212](../fraud_flow/templates/dashboard.html#L212). Nên thêm link có nhãn rõ và giữ focus case khi đổi giới hạn danh sách.

### 8. P3 — Ngôn ngữ và thứ bậc thông tin chưa thống nhất

Thanh điều hướng dùng Portal / Live Demo / Control Room / API Workspace / Research, nội dung trộn tiếng Việt với tiếng Anh. Trên mobile header chiếm khoảng 360 px và thiếu đường dẫn review queue trực tiếp. Trang chủ có khoảng trống lớn do hero giãn bằng chiều cao thẻ thống kê bên cạnh.

Nguồn: [_app_header.html:24](../fraud_flow/templates/_app_header.html#L24), [home.html](../fraud_flow/templates/home.html). Nên thống nhất nhãn theo tác vụ: Trang chủ, Giao dịch, Giám sát, Xác minh, Tài liệu, Nghiên cứu; rút gọn header và nội dung giới thiệu trên mobile. Giữ các thuật ngữ chuyên môn khi cần, kèm diễn giải ngắn.

## Kết quả kiểm tra và giới hạn

- 18 lượt tải trang/viewport đều HTTP 200; không ghi nhận JavaScript `pageerror` trong các màn hình đã thử.
- Axe không phát hiện vi phạm thuộc tập WCAG A/AA đã chọn ở sáu trang desktop; mobile phát hiện các vùng cuộn nêu trên. Đây không phải chứng nhận accessibility: vẫn cần thử screen reader, bàn phím và người dùng thật.
- Bố cục không làm tràn toàn trang ở năm màn còn lại trong ba kích thước đã thử. Bảng research/docs có cuộn ngang bên trong vùng chứa; đây là hành vi khác với tràn toàn trang của dashboard.
- Review JSON/XLSX và API vẫn truy cập được, nhưng điều đó chưa thay thế một luồng review hoàn chỉnh trên UI.
- Dữ liệu thử và giao dịch phát sinh chỉ nằm ở bản sao tạm. Mã UI, model và log production được giữ nguyên.

[Kết quả đo và axe chi tiết trước khi sửa](ui-audit/results.json) · [Giao diện NCKH hiện tại và ảnh minh họa](DEMO_NCKH.md).

Ảnh UI/UX trước khi cập nhật đã được xóa; ảnh phiên bản NCKH hiện tại được giữ tại `ui-audit/nckh/`.
