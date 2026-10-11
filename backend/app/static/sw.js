/* Service worker: cache app shell for offline viewing (reports/shell only). */
const CACHE = "asalah-v1";
const SHELL = ["/login", "/dashboard", "/static/css/variables.css",
  "/static/css/components.css", "/static/js/main.js"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET" || e.request.url.includes("/api/")) return;
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy));
      return res;
    }).catch(() => caches.match("/dashboard"))));
});
