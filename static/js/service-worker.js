self.addEventListener("push", function (event) {
  var data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (error) {
      data = { body: event.data.text() };
    }
  }

  var title = data.title || "Mầm Wellbeing";
  var options = {
    body: data.body || "Bạn có một thông báo mới.",
    data: { url: data.url || "/notifications/" },
    tag: data.id || undefined,
  };
  event.waitUntil(
    self.registration.showNotification(title, options).then(function () {
      return self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (clients) {
        clients.forEach(function (client) {
          client.postMessage({ type: "wellbeing-push", title: title, body: options.body });
        });
      });
    })
  );
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var url = event.notification.data.url || "/notifications/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (clients) {
      for (var i = 0; i < clients.length; i += 1) {
        if ("focus" in clients[i]) {
          clients[i].navigate(url);
          return clients[i].focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});
