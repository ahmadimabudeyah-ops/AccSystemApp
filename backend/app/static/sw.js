/* Service worker: cache app shell for offline viewing (reports/shell only).
   v2: JS uses network-first so the browser never runs a stale save-handler. */
const CACHE = "asalah-v2";
const SHELL = ["/login", "/dashboard", "/static/css/variables.css",
  "/static/css/components.css", "/static/js/main.js?v=2"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
});
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET" || e.request.url.includes("/api/")) return;
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/static/js/")) {
    // الشبكة أولًا لملفات السكربت، والكاش احتياط فقط.
    e.respondWith(fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy));
      return res;
    }).catch(() => caches.match(e.request)));
    return;
  }
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy));
      return res;
    }).catch(() => caches.match("/dashboard"))));
});
