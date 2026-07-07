(() => {
  const replacements = new Map([
    ["Schemas", "Lược đồ"],
    ["Models", "Mô hình dữ liệu"],
    ["Authorize", "Phân quyền"],
    ["Try it out", "Thử ngay"],
    ["Execute", "Chạy"],
    ["Cancel", "Hủy"],
    ["Clear", "Xóa"],
    ["Responses", "Phản hồi"],
    ["Response content type", "Kiểu dữ liệu phản hồi"],
    ["Parameters", "Tham số"],
    ["No parameters", "Không có tham số"],
    ["Request body", "Nội dung gửi lên"],
    ["Example Value", "Ví dụ"],
    ["Schema", "Lược đồ"],
    ["Description", "Mô tả"],
    ["Required", "Bắt buộc"],
    ["Server response", "Phản hồi máy chủ"],
    ["Response headers", "Header phản hồi"],
    ["Request URL", "URL yêu cầu"],
    ["Request duration", "Thời gian xử lý"],
    ["Curl", "Lệnh curl"],
    ["Code", "Mã"],
    ["Details", "Chi tiết"],
    ["Successful Response", "Phản hồi thành công"],
    ["Available authorizations", "Các kiểu phân quyền"],
    ["Name", "Tên"],
  ]);

  const translateNode = (node) => {
    if (!node || node.nodeType !== Node.TEXT_NODE) return;
    const text = node.textContent.trim();
    if (!text) return;
    if (replacements.has(text)) {
      node.textContent = node.textContent.replace(text, replacements.get(text));
    }
  };

  const translateTree = () => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let current;
    while ((current = walker.nextNode())) {
      translateNode(current);
    }
    document.querySelectorAll("input[placeholder='Filter by tag']").forEach((el) => {
      el.placeholder = "Lọc theo nhóm endpoint";
    });
  };

  const observer = new MutationObserver(() => translateTree());
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("load", translateTree);
  setInterval(translateTree, 1000);
})();
