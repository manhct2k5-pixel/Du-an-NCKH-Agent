# LLM và giải thích trong bản demo NCKH

## Trạng thái đã kiểm tra

Trong đợt kiểm tra đầu ngày 09/11/2026, môi trường chưa có `OPENAI_API_KEY` và chưa cài `langchain-openai`. Nhánh medium chạy ReAct với các lớp heuristic local. Đây là luật xử lý bằng Python, không phải một mô hình ngôn ngữ được huấn luyện. XGBoost vẫn chấm điểm thật; các công cụ vẫn truy vấn lịch sử trong feature store của phiên chạy.

Đợt chuẩn bị API sau đó đã cài SDK, kiểm tra tương thích và thêm hỗ trợ **DeepSeek** theo yêu cầu. API key đã được cấu hình trong `.env` local. Lần gọi thật ngày 09/11/2026 trả về **HTTP 402 — không đủ số dư**, không có câu trả lời từ model. Chưa kiểm chứng được luồng medium với LLM qua mạng vì tài khoản chưa đủ số dư. [Kết quả đã loại thông tin nhạy cảm](ui-audit/nckh/deepseek-api-check.json) · [Ý nghĩa mã lỗi DeepSeek](https://api-docs.deepseek.com/quick_start/error_codes/).

Các trường `llm_*` được tính bằng hàm heuristic có tính tái lập trong `fraud_flow/llm_features.py`. Tên trường không chứng minh có cuộc gọi LLM. B8/B11 offline replay và thời gian chạy local không chứng minh hiệu năng của LLM qua mạng.

**Cập nhật 10/11/2026:** đã thử thành công DeepSeek Web qua cầu nối **DS2API**, dùng token phiên đã đăng nhập. `.env` hiện tại chọn `ds2api`. Lệnh kiểm tra đã nhận `API_OK` thật; mẫu medium chạy 4 công cụ, nhận 6 phản hồi model qua API và trả quyết định review. [Cách chạy và bằng chứng DS2API](DS2API_SETUP.md). Kết quả HTTP 402 ở trên thuộc đường API chính thức trước đó.

## Tự đối chiếu trên ứng dụng

1. Mở `/llm/status`. `configuration` cho biết cấu hình; `decision_runtime` là các sự kiện model quan sát được từ khi tiến trình khởi động. Endpoint không gọi API thử và không trả về khóa.
2. Chạy mẫu **Trung bình**. Khối **Agent có thực sự chạy?** cho biết backend, số công cụ và phản hồi. JSON `agent.execution.stages` tách ReAct, quyết định có cấu trúc và sửa JSON.
3. Khi chạy local, mẫu medium với lịch sử trống thực hiện 4 công cụ và 6 phản hồi heuristic (4 lượt chọn công cụ, 1 kết thúc ReAct, 1 quyết định JSON). `external_response_observed=false`.
4. Low/high bỏ qua ReAct khi ra quyết định. High bị block có thể tạo nội dung hậu kiểm bất đồng bộ, đếm riêng tại `post_decision_log_runtime`; nội dung này không tham gia quyết định.

Bộ đếm qua API chỉ tăng khi callback báo model qua API trả về thành công. Trường `backend` và `providers_observed` phân biệt `ds2api`, `deepseek` và `openai` theo endpoint và cấu hình thực tế. Có key hoặc SDK chưa đủ để báo LLM đã hoạt động. Lỗi gọi model được đếm riêng. Log cũ thiếu `agent.execution` được ghi là chưa có bằng chứng thực thi. Bộ đếm tổng đặt lại khi khởi động lại; metadata từng giao dịch được lưu trong log mới.

`attempts` đếm lượt gọi model ở LangChain, không đếm riêng HTTP retry nội bộ của SDK.

## Nguồn lời giải thích

Phần trình bày dùng `grounded_template_v2`: tổng hợp tiếng Việt từ prediction, lookup, kết quả công cụ và quyết định cuối sau chính sách. Đây là cách trình bày dữ kiện, không phải văn bản tự do do LLM sinh. Nội dung gốc của agent nằm trong `agent.agent_output` để đối chiếu.

- Tách điểm vận hành với xác suất gốc: điểm `0.700` không có nghĩa 70% gian lận; mẫu medium có xác suất gốc khoảng `0.0688%`.
- Gộp các cờ thiết bị trùng nhau khi trình bày, giữ mã lý do để xử lý máy.
- Dữ liệu thiếu không được coi là lịch sử bằng 0. Chỉ nói IP không có trong blacklist khi công cụ trả về `false`; điều đó chưa chứng minh an toàn.
- Hiển thị nguồn dữ kiện; SHAP có chiều tăng/giảm và đóng góp trên thang đầu ra mô hình, không quy thành phần trăm xác suất.
- Confidence chưa hiệu chuẩn, không diễn giải là độ chính xác. Chặn, review và step-up chưa xác nhận nhãn thật.

## Bật DeepSeek qua API

1. Tạo API key tại [DeepSeek Platform](https://platform.deepseek.com/api_keys). API DeepSeek yêu cầu key riêng, không dùng key OpenAI. [Tài liệu DeepSeek](https://api-docs.deepseek.com/).
2. Điền key trực tiếp vào file `.env` ở gốc dự án (file này được Git bỏ qua). Không gửi key qua chat. `.env.example` chỉ chứa mẫu rỗng:

   ```dotenv
   FRAUD_LLM_PROVIDER=deepseek
   DEEPSEEK_API_KEY=your_key_here
   FRAUD_LLM_MODEL=deepseek-flash
   ```

3. Cài gói tùy chọn nếu dùng môi trường mới; môi trường `.venv` hiện tại đã cài:

   ```bash
   .venv/bin/python -m pip install -r requirements-openai.txt
   .venv/bin/python -m pip check
   ```

4. Thử **một cuộc gọi API thật** bằng nội dung kiểm tra đơn giản, không gửi giao dịch:

   ```bash
   .venv/bin/python run_fraud_flow.py llm-check
   ```

   Kết quả phải có `status=ok`, phản hồi `API_OK`, `external_response_observed=true`, `providers_observed=["deepseek"]`. Khi thiếu key, sai key, hết quota hoặc lỗi mạng, lệnh báo lỗi và thoát; không chuyển sang heuristic. Lệnh này có bộ đếm riêng trong tiến trình kiểm tra, không làm tăng bộ đếm của server.

5. Chạy server bằng chế độ bắt buộc API:

   ```bash
   .venv/bin/python run_fraud_flow.py serve --llm-api
   ```

   Mở `http://127.0.0.1:8000/transaction/form`, chạy mẫu medium rồi xem `external_response_observed` và tên provider trong **chính giao dịch đó**. `/llm/status` cho biết bộ đếm của server. Sau khi sửa `.env`, khởi động lại server. Có thể chỉ định file bằng `--env-file /duong/dan/.env`; biến đã export trong terminal được ưu tiên hơn file.

Tích hợp dùng SDK tương thích OpenAI, endpoint chính thức `https://api.deepseek.com`, model `deepseek-flash`. Chế độ `thinking` được tắt cho luồng ReAct văn bản hiện tại. Các tham số này dựa trên [DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/). Timeout 30 giây, tối đa 1 lần thử lại ở client; tắt cache và streaming. Message được chuyển thành văn bản trước khi parse JSON. Không thay bộ đặc trưng offline hoặc model XGBoost.

Chọn model chung bằng `FRAUD_LLM_MODEL`, hoặc từng bước bằng `FRAUD_REACT_MODEL`, `FRAUD_DECISION_MODEL`, `FRAUD_RETRY_MODEL`, `FRAUD_HIGH_RISK_MODEL`. Không dùng tên model của nhà cung cấp khác.

Để dùng OpenAI: đặt `FRAUD_LLM_PROVIDER=openai`, `OPENAI_API_KEY` và `FRAUD_LLM_MODEL=gpt-4.1-mini`. [OpenAI quickstart](https://developers.openai.com/api/docs/quickstart).

Kiểm thử đã chạy qua SDK đã cài với HTTP mô phỏng cho cả OpenAI và DeepSeek, gồm tuần tự ReAct, truy vấn 4 công cụ, parse JSON và ghi nhận backend đúng. Đây là bằng chứng tích hợp local; chưa phải bằng chứng kết nối tới máy chủ ngoài. Chế độ API gửi ngữ cảnh giao dịch và kết quả công cụ cho nhà cung cấp.

API của ứng dụng chuyển lỗi nhà cung cấp thành thông báo rõ trên form: sai key, thiếu số dư, model không tồn tại hoặc bị giới hạn. Không trả raw error body hay tạo quyết định giả khi API lỗi. Với HTTP 402, phản hồi gateway là HTTP 503 kèm `error_code=llm_insufficient_balance`, `upstream_status=402`; dữ liệu nhập được giữ lại.
