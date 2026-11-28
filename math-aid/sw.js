const CACHE = 'mathaid-v2';
const ASSETS = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png'];

self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE)
            .then((c) => c.addAll(ASSETS))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (e) => {
    if (e.request.method !== 'GET') return;
    // Navigationer (HTML): net først, så brugere altid får nyeste kode — fallback til cache ved offline.
    if (e.request.mode === 'navigate') {
        e.respondWith(
            fetch(e.request).then((resp) => {
                if (resp && resp.ok && new URL(e.request.url).origin === location.origin) {
                    const copy = resp.clone();
                    caches.open(CACHE).then((c) => c.put(e.request, copy));
                }
                return resp;
            }).catch(() =>
                caches.match(e.request).then((hit) => hit || caches.match('./index.html'))
            )
        );
        return;
    }
    // Øvrige assets: cache først, ellers net + gem i cache.
    e.respondWith(
        caches.match(e.request).then((hit) => {
            if (hit) return hit;
            return fetch(e.request).then((resp) => {
                if (resp && resp.ok && new URL(e.request.url).origin === location.origin) {
                    const copy = resp.clone();
                    caches.open(CACHE).then((c) => c.put(e.request, copy));
                }
                return resp;
            }).catch(() => caches.match('./index.html'));
        })
    );
});
