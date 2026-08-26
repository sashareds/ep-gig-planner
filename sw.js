const CACHE = "ep26-v4";
const SHELL = [
  "./",
  "./index.html",
  "./styles.css",
  "./css/variables.css",
  "./css/document.css",
  "./css/composition.css",
  "./css/blocks.css",
  "./css/utilities.css",
  "./app.js",
  "./manifest.webmanifest",
  "./img/hero.svg",
  "./img/icon-192.png",
  "./data/ep26.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then((resp) => {
        if (resp.ok) {
          const copy = resp.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return resp;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match("./index.html")))
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = event.notification.data?.url || "./";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      if (windows[0]) return windows[0].focus();
      if (self.clients.openWindow) return self.clients.openWindow(target);
      return undefined;
    })
  );
});
