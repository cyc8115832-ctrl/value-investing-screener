// 價值投資選股 App - Service Worker (sw.js)
const CACHE_NAME = 'value-investing-evidence-v2-2026-10-08T09:52:50.145703+00:00';
const ASSETS_TO_CACHE = [
  './index.html',
  './manifest.json',
  './icon.svg'
  ,'./value-ui.css', './value-ui.js', './static-adapter.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET' || new URL(event.request.url).origin !== self.location.origin) return;
  // 對於 API 請求採取 Network First，保證即時價格資料
  if (event.request.url.includes('/api/')) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(JSON.stringify({ error: "目前處於離線狀態，無法取得最新即時行情" }), {
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );
    return;
  }

  // 靜態頁面採取 Network First with Cache Fallback
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
