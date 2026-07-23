self.addEventListener("push", (event) => {
  const dados = event.data ? event.data.json() : {};
  event.waitUntil(
    self.registration.showNotification(dados.title || "Sinal ao vivo", {
      body: dados.body || "",
      icon: "/static/icon-192.png",
      badge: "/static/icon-192.png",
      data: { url: dados.url || "/" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url || "/"));
});
