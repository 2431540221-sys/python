(function () {
  var form = document.getElementById("push-controls");
  if (!form) return;

  var enableButton = document.getElementById("push-enable");
  var disableButton = document.getElementById("push-disable");
  var status = document.getElementById("push-status");
  var csrf = form.querySelector("[name=csrfmiddlewaretoken]").value;
  var endpoint = "/notifications/push-subscription/";

  function setStatus(message) {
    status.textContent = message;
  }

  function publicKeyBytes(value) {
    var padding = "=".repeat((4 - value.length % 4) % 4);
    var base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
    var raw = window.atob(base64);
    var bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
    return bytes;
  }

  function saveSubscription(method, subscription) {
    return fetch(endpoint, {
      method: method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(subscription),
    }).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok) throw new Error(data.error || "Không lưu được đăng ký push.");
        return data;
      });
    });
  }

  enableButton.addEventListener("click", function () {
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
      setStatus("Trình duyệt này chưa hỗ trợ Web Push.");
      return;
    }

    enableButton.disabled = true;
    setStatus("Đang đăng ký thông báo…");
    var permission = Notification.permission === "default"
      ? Notification.requestPermission()
      : Promise.resolve(Notification.permission);
    permission.then(function (result) {
      if (result !== "granted") throw new Error("Bạn chưa cấp quyền thông báo cho trình duyệt.");
      return navigator.serviceWorker.register("/service-worker.js");
    }).then(function (registration) {
      return registration.pushManager.getSubscription().then(function (subscription) {
        if (subscription) return subscription;
        return registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: publicKeyBytes(enableButton.getAttribute("data-vapid-key")),
        });
      });
    }).then(function (subscription) {
      return saveSubscription("POST", subscription.toJSON());
    }).then(function () {
      setStatus("Đã bật thông báo đẩy trên trình duyệt này.");
    }).catch(function (error) {
      setStatus(error.message || "Không bật được thông báo đẩy.");
    }).then(function () {
      enableButton.disabled = false;
    });
  });

  disableButton.addEventListener("click", function () {
    if (!("serviceWorker" in navigator)) {
      setStatus("Trình duyệt này chưa hỗ trợ Web Push.");
      return;
    }

    disableButton.disabled = true;
    navigator.serviceWorker.getRegistration("/").then(function (registration) {
      return registration ? registration.pushManager.getSubscription() : null;
    }).then(function (subscription) {
      if (!subscription) {
        setStatus("Trình duyệt này không có đăng ký push đang hoạt động.");
        return;
      }
      return saveSubscription("DELETE", { endpoint: subscription.endpoint }).then(function () {
        return subscription.unsubscribe();
      }).then(function () {
        setStatus("Đã tắt thông báo đẩy trên trình duyệt này.");
      });
    }).catch(function (error) {
      setStatus(error.message || "Không tắt được thông báo đẩy.");
    }).then(function () {
      disableButton.disabled = false;
    });
  });
})();
