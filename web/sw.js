// Service worker: make the on-device app truly offline-capable.
// App shell (pages, CSS, JS, WASM, SQLite runtime) is precached
// versioned; same-origin requests are cache-first once stored; Google
// Fonts are stale-while-revalidated (progressive enhancement only).
// No computation or storage behavior changes: the engine and the
// month store already run fully on-device.
const CACHE = 'monthly-planner-v1';

const SHELL = [
  '.',
  'index.html',
  'income.html',
  'expenses.html',
  'plan.html',
  'months.html',
  'disclaimer.html',
  'manifest.webmanifest',
  'app/app.css',
  'app/chrome.js',
  'app/engine.js',
  'app/advice.js',
  'store/store.js',
  'store/grain.js',
  'store/schema.sql',
  'engine/pkg-web/budget_wasm.js',
  'engine/pkg-web/budget_wasm_bg.wasm',
  'vendor/wa-sqlite/dist/wa-sqlite.mjs',
  'vendor/wa-sqlite/dist/wa-sqlite.wasm',
  'vendor/wa-sqlite/dist/wa-sqlite-async.mjs',
  'vendor/wa-sqlite/dist/wa-sqlite-async.wasm',
  'vendor/wa-sqlite/src/sqlite-api.js',
  'vendor/wa-sqlite/src/sqlite-constants.js',
  'vendor/wa-sqlite/src/VFS.js',
  'vendor/wa-sqlite/src/examples/WebLocks.js',
  'vendor/wa-sqlite/src/examples/IDBContext.js',
  'vendor/wa-sqlite/src/examples/IDBBatchAtomicVFS.js',
  'vendor/wa-sqlite/src/examples/OriginPrivateFileSystemVFS.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      const scope = self.registration.scope;
      await cache.addAll(SHELL.map((p) => new URL(p, scope).href));
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys()) {
        if (key !== CACHE) await caches.delete(key);
      }
      await self.clients.claim();
    })(),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin === self.location.origin) {
    // App shell and data runtime: cache-first, populate on first load.
    event.respondWith(
      (async () => {
        const cache = await caches.open(CACHE);
        const hit = await cache.match(request);
        if (hit) return hit;
        const res = await fetch(request);
        if (res.ok) cache.put(request, res.clone());
        return res;
      })(),
    );
  } else if (url.hostname.endsWith('fonts.googleapis.com') || url.hostname.endsWith('fonts.gstatic.com')) {
    // Fonts only: serve stale while revalidating; the app never depends on them.
    event.respondWith(
      (async () => {
        const cache = await caches.open(CACHE);
        const hit = await cache.match(request);
        const refresh = fetch(request)
          .then((res) => {
            if (res.ok) cache.put(request, res.clone());
            return res;
          })
          .catch(() => hit);
        return hit || refresh;
      })(),
    );
  }
});
