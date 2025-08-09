const CACHE_NAME = 'mabarati-korlapda-cache-v2';
const URLS_TO_CACHE = [
    '/lapangan/',
    '/lapangan/login',
];

self.addEventListener('install', event => {
    event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(URLS_TO_CACHE)));
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => response || fetch(event.request))
    );
});

// --- LOGIKA SINKRONISASI OTOMATIS ---
self.addEventListener('sync', event => {
    if (event.tag === 'sync-absen') {
        event.waitUntil(syncAbsenData());
    }
});

async function syncAbsenData() {
    importScripts('https://unpkg.com/dexie@3/dist/dexie.js');
    const db = new Dexie('MabarAtiKorlapdaDB');
    db.version(1).stores({ absenQueue: '++id, &[pendaftaran_id+nama_absen], status' });

    const absenToSync = await db.absenQueue.toArray();
    if (absenToSync.length === 0) return;

    // Kelompokkan data berdasarkan nama_absen
    const groupedAbsen = absenToSync.reduce((acc, current) => {
        (acc[current.nama_absen] = acc[current.nama_absen] || []).push(current);
        return acc;
    }, {});

    const formData = new FormData();
    for (const namaAbsen in groupedAbsen) {
        const hadirIds = groupedAbsen[namaAbsen]
            .filter(item => item.status === 'Hadir')
            .map(item => item.pendaftaran_id);
        
        hadirIds.forEach(id => {
            formData.append(`hadir-${namaAbsen}`, id);
        });
    }

    try {
        const response = await fetch('/lapangan/simpan-absen', {
            method: 'POST',
            body: formData,
        });

        if (response.ok) {
            console.log('Sinkronisasi absen berhasil!');
            await db.absenQueue.clear();
            self.clients.matchAll().then(clients => {
                clients.forEach(client => client.postMessage({ type: 'SYNC_SUCCESS' }));
            });
        }
    } catch (error) {
        console.error('Gagal mengirim data saat sinkronisasi:', error);
    }
}