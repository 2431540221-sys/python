// Hỏi xác nhận trước khi gửi các form có data-confirm (xóa dữ liệu...).
document.addEventListener("submit", function (event) {
  var message = event.target.getAttribute("data-confirm");
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});
