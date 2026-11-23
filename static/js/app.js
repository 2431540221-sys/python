// Hỏi xác nhận trước khi gửi các form có data-confirm (xóa dữ liệu...).
document.addEventListener("submit", function (event) {
  var message = event.target.getAttribute("data-confirm");
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.addEventListener("message", function (event) {
    if (!event.data || event.data.type !== "wellbeing-push") return;
    var link = document.querySelector('.navlink[href$="/notifications/"]');
    if (!link) return;
    var badge = link.querySelector(".navbadge");
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "navbadge";
      link.appendChild(badge);
    }
    badge.textContent = String((parseInt(badge.textContent, 10) || 0) + 1);
    badge.setAttribute("aria-label", "thông báo chưa đọc");
  });
}
