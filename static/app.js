// Grot2Buy — Frontend
const API = '/api';
let currentTab = 'synced';
let categories = [];

// Übersetzungs-Hilfe (wird aus window._t gespeist, das im Template gesetzt wird)
function __(key, ...args) {
    let msg = window._t?.[key];
    if (msg === undefined) return key;
    if (args.length === 1 && typeof args[0] === 'object' && args[0] !== null) {
        for (const [k, v] of Object.entries(args[0])) {
            msg = msg.split(`{${k}}`).join(v);
        }
    }
    return msg;
}

// ─── Dark Mode ────────────────────────────────────────────────

function applyTheme(theme) {
    if (theme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else if (theme === 'light') {
        document.documentElement.removeAttribute('data-theme');
    } else {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (prefersDark) {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }
    }
}

function toggleDarkMode(theme) {
    if (!theme) {
        const current = localStorage.getItem('grot2buy_theme') || 'auto';
        if (current === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            theme = 'light';
        } else if (current === 'auto') {
            theme = 'dark';
        } else if (current === 'dark') {
            theme = 'light';
        } else {
            theme = 'auto';
        }
    }
    localStorage.setItem('grot2buy_theme', theme);
    applyTheme(theme);
    updateDarkModeBtn();
    const sel = document.getElementById('darkModeSelect');
    if (sel) sel.value = theme;
}

function updateDarkModeBtn() {
    const btn = document.getElementById('darkModeBtn');
    if (!btn) return;
    const theme = localStorage.getItem('grot2buy_theme') || 'auto';
    const sel = document.getElementById('darkModeSelect');
    if (sel) sel.value = theme;
    if (theme === 'dark') {
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    } else {
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
    }
}

// ─── Push Notifications ───────────────────────────────────────

async function requestNotificationPermission() {
    if (!('Notification' in window) || !navigator.serviceWorker?.controller) return;
    if (Notification.permission === 'default') {
        await Notification.requestPermission();
    }
}

async function sendNotification(title, body) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    if (navigator.serviceWorker?.controller) {
        navigator.serviceWorker.controller.postMessage({ type: 'show-notification', title, body });
    }
}

// ─── WebSocket ───────────────────────────────────────────────

let ws = null;
let wsReconnectAttempts = 0;
const WS_MAX_RECONNECT = 20;

function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onopen = () => {
        if (wsReconnectAttempts > 0 || !lastSyncOk) {
            loadItems();
            loadLists();
        }
        wsReconnectAttempts = 0;
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            switch (msg.type) {
                case 'sync_complete':
                    lastSyncTime = msg.timestamp;
                    localStorage.setItem('grot2buy_last_sync', msg.timestamp);
                    updateSyncStatus(true, formatTime(msg.timestamp));
                    loadItems();
                    loadLists();
                    break;
                case 'items_updated':
                    loadItems();
                    loadLists();
                    break;
            }
        } catch (e) {
            console.error('WS message error:', e);
        }
    };

    ws.onclose = () => {
        ws = null;
        if (wsReconnectAttempts < WS_MAX_RECONNECT) {
            wsReconnectAttempts++;
            setTimeout(connectWebSocket, Math.min(1000 * wsReconnectAttempts, 10000));
        }
    };

    ws.onerror = () => {
        ws?.close();
    };
}

// ─── Init ────────────────────────────────────────────────────

// Service Worker sofort aktualisieren, falls neue Version wartet
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').then((reg) => {
        if (reg.waiting) {
            reg.waiting.postMessage({ type: 'SKIP_WAITING' });
        }
        reg.addEventListener('updatefound', () => {
            const newWorker = reg.installing;
            newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                    newWorker.postMessage({ type: 'SKIP_WAITING' });
                }
            });
        });
    });
}

let lastSyncOk = false;
let lastSyncTime = null;
let syncTimer = null;

function startSyncTimer(intervalMin) {
    if (syncTimer) clearInterval(syncTimer);
    const ms = (intervalMin > 0 ? intervalMin : 2) * 60 * 1000;
    syncTimer = setInterval(refreshPillTime, ms);
}

function refreshPillTime() {
    if (!lastSyncTime) return;
    const text = document.getElementById('pillText');
    if (text) text.textContent = formatTime(lastSyncTime);
}

function updateSyncStatus(ok, timeStr) {
    const pill = document.getElementById('syncStatus');
    const text = document.getElementById('pillText');
    if (!pill || !text) return;

    if (ok) {
        pill.dataset.status = 'ok';
        text.textContent = timeStr || __('sync.status_ok');
    } else {
        pill.dataset.status = 'error';
        text.textContent = __('sync.status_never');
    }
}

function formatTime(iso) {
    if (!iso) return '';
    const now = Date.now();
    const then = new Date(iso).getTime();
    const diff = Math.floor((now - then) / 1000);
    if (diff < 60) return __('sync.just_now');
    if (diff < 3600) return Math.floor(diff / 60) + 'm';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h';
    return Math.floor(diff / 86400) + 'd';
}

document.addEventListener('DOMContentLoaded', async () => {
    applyTheme(localStorage.getItem('grot2buy_theme') || 'auto');
    updateDarkModeBtn();
    requestNotificationPermission();
    connectWebSocket();

    const lastSync = localStorage.getItem('grot2buy_last_sync');
    if (lastSync) {
        updateSyncStatus(true, formatTime(lastSync));
    }
    startSyncTimer(2);

    // Data first, sync im Hintergrund
    await Promise.all([
        loadCategories(),
        loadLists(),
        loadItems(),
    ]);

    api('/sync/full').then(result => {
        const now = new Date().toISOString();
        localStorage.setItem('grot2buy_last_sync', now);
        updateSyncStatus(true, formatTime(now));
        lastSyncOk = true;
        lastSyncTime = now;
        return Promise.all([
            loadCategories(),
            loadLists(),
            loadItems(),
        ]);
    }).catch(e => {
        console.error('Initial sync failed:', e);
        updateSyncStatus(false);
    });
});

// ─── Pull to Refresh ─────────────────────────────────────────

(function() {
    let startY = 0;
    let pulling = false;
    const threshold = 100;
    const app = document.querySelector('.app');

    app.addEventListener('touchstart', (e) => {
        if (window.scrollY > 0) return;
        startY = e.touches[0].clientY;
        pulling = true;
    }, { passive: true });

    app.addEventListener('touchmove', (e) => {
        if (!pulling) return;
        const dy = e.touches[0].clientY - startY;
        if (dy > 20) {
            e.preventDefault();
        }
    }, { passive: false });

    app.addEventListener('touchend', (e) => {
        if (!pulling) return;
        pulling = false;
        const dy = e.changedTouches[0].clientY - startY;
        if (dy > threshold) {
            syncWithBAP();
        }
    }, { passive: true });
})();

// ─── API Helpers ─────────────────────────────────────────────

// ─── Offline Support ────────────────────────────────────────

function getOfflineQueue() {
    try { return JSON.parse(localStorage.getItem('grot2buy_offline_queue') || '[]'); }
    catch { return []; }
}

function addToOfflineQueue(path, opts) {
    const queue = getOfflineQueue();
    queue.push({ path, method: opts?.method || 'GET', body: opts?.body ? JSON.parse(opts.body) : null, timestamp: Date.now() });
    localStorage.setItem('grot2buy_offline_queue', JSON.stringify(queue));
    updateOfflineBadge();
}

async function processOfflineQueue() {
    const queue = getOfflineQueue();
    if (queue.length === 0) return;
    localStorage.removeItem('grot2buy_offline_queue');
    updateOfflineBadge();
    for (const op of queue) {
        try {
            await fetch(`${API}${op.path}`, {
                method: op.method,
                headers: { 'Content-Type': 'application/json' },
                body: op.body ? JSON.stringify(op.body) : undefined,
            });
        } catch {
            addToOfflineQueue(op.path, { method: op.method, body: op.body ? JSON.stringify(op.body) : undefined });
            break;
        }
    }
    loadItems();
}

function updateOfflineBadge() {
    const badge = document.getElementById('offlineBadge');
    const queue = getOfflineQueue();
    const count = queue.length;
    if (!navigator.onLine) {
        badge.textContent = count > 0 ? `📴 ${count}` : '📴';
        badge.classList.add('show');
    } else if (count > 0) {
        badge.textContent = `⏳ ${count}`;
        badge.classList.add('show');
    } else {
        badge.classList.remove('show');
    }
}

window.addEventListener('online', () => { updateOfflineBadge(); processOfflineQueue(); });
window.addEventListener('offline', updateOfflineBadge);

// ─── API ────────────────────────────────────────────────────

async function api(path, opts = {}) {
    try {
        const res = await fetch(`${API}${path}`, {
            headers: { 'Content-Type': 'application/json' },
            ...opts,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) {
        if (opts.method && opts.method !== 'GET') {
            addToOfflineQueue(path, opts);
            return { result: __('offline.queued'), offline: true };
        }
        throw e;
    }
}

function toast(msg, duration = 3000) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), duration);
}

function undoToast(msg, undoAction, duration = 5000) {
    const container = document.getElementById('toastContainer');
    const el = document.createElement('div');
    el.className = 'undo-toast';
    el.innerHTML = `<span class="undo-toast-msg">${escapeHtml(msg)}</span><button class="undo-toast-btn">${__('item.undo')}</button>`;
    container.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    let done = false;
    const cleanup = () => { if (!done) { done = true; el.classList.remove('show'); setTimeout(() => el.remove(), 300); } };
    el.querySelector('.undo-toast-btn').onclick = async () => {
        cleanup();
        await undoAction();
        toast(__('item.restored'));
        loadItems();
    };
    setTimeout(cleanup, duration);
}

async function downloadFile(url, filename) {
    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
        toast( __('download.success', {filename: filename}) );
    } catch (e) {
        toast( __('download.failed', {msg: e.message}) );
    }
}

// ─── Categories ──────────────────────────────────────────────

async function loadCategories() {
    try {
        const data = await api('/categories');
        categories = data.categories || [];
        const sel = document.getElementById('itemCategory');
        sel.innerHTML = '<option value="">' + __('add_modal.category_auto') + '</option>' +
            categories.map(c => `<option value="${c}">${c}</option>`).join('');
    } catch (e) {
        console.error('Categories load failed:', e);
    }
}

// ─── Lists (Tabs) ───────────────────────────────────────────

async function loadLists() {
    try {
        const data = await api('/lists');
        const tabs = document.getElementById('listTabs');
        const lists = data.lists || [];

        let html = '<button class="tab active" data-list="synced" onclick="switchTab(\'synced\', this)"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:3px"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>' + __('tab.synced') + ' (' + (data.synced_count || 0) + ')</button>';
        html += '<button class="tab" data-list="grocy" onclick="switchTab(\'grocy\', this)"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:3px"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>' + __('tab.grocy') + ' (' + (data.grocy_count || 0) + ')</button>';
        for (const list of lists) {
            html += `<button class="tab" data-list="${list.id}" onclick="switchTab('${list.id}', this)"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:3px"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>${list.name} (${list.count})</button>`;
        }
        tabs.innerHTML = html;
    } catch (e) {
        console.error('Lists load failed:', e);
    }
}

function switchTab(tab, btn) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    loadItems();
}

// ─── Items ───────────────────────────────────────────────────

async function loadItems() {
    const content = document.getElementById('content');
    content.innerHTML = '<div class="loading"><div class="spinner"><div class="spinner-dot"></div><div class="spinner-dot"></div><div class="spinner-dot"></div><div class="spinner-dot"></div><div class="spinner-dot"></div><div class="spinner-dot"></div><div class="spinner-dot"></div></div><p>' + __('loading.data') + '</p></div>';

    try {
        let data;
        if (currentTab === 'synced') {
            data = await api('/synced/items');
            renderSyncedItems(data);
        } else if (currentTab === 'grocy') {
            data = await api('/sync/grocy');
            renderGrocyItems(data);
        } else {
            data = await api(`/lists/${currentTab}/items`);
            renderBAPItems(data);
        }
    } catch (e) {
        showOfflineFallback();
    }
}

async function showOfflineFallback() {
    const content = document.getElementById('content');
    try {
        const cache = await caches.open('grot2buy-v15');
        const req = new Request('/api/synced/items');
        const cached = await cache.match(req);
        if (cached) {
            const data = await cached.json();
            renderSyncedItems(data);
            toast(__('offline.cached'));
            return;
        }
    } catch {}
    content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>' + __('error.load_title') + '</h3><p>' + __('error.load_text') + '</p></div>';
}

function renderSyncedItems(data) {
    const content = document.getElementById('content');
    const items = data.items || [];
    const byCategory = data.by_category || {};

    document.getElementById('itemCountValue').textContent = items.length;

    if (items.length === 0) {
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🛒</div><h3>' + __('empty.synced_title') + '</h3><p>' + __('empty.synced_text') + '</p></div>';
        return;
    }

    const sortedCategories = Object.keys(byCategory).sort((a, b) => a.localeCompare(b));

    content.innerHTML = `
        <div class="item-list">
            ${sortedCategories.map(cat => {
                const catItems = byCategory[cat];
                const sortedItems = catItems.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
                return `
                    <div class="category-group">
                        <div class="category-header">${escapeHtml(cat)} <span class="category-count">${sortedItems.length}</span></div>
                        ${sortedItems.map(item => renderItem(item)).join('')}
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

function renderBAPItems(data) {
    const content = document.getElementById('content');
    const items = data.items || [];

    document.getElementById('itemCountValue').textContent = items.length;

    if (items.length === 0) {
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📋</div><h3>' + __('empty.bap_title') + '</h3></div>';
        return;
    }

    content.innerHTML = `
        <div class="item-list">
            ${items.map(item => renderBAPItem(item)).join('')}
        </div>
    `;
}

function renderGrocyItems(data) {
    const content = document.getElementById('content');
    const items = data.items || [];

    document.getElementById('itemCountValue').textContent = items.length;

    if (items.length === 0) {
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📦</div><h3>' + __('empty.grocy_title') + '</h3></div>';
        return;
    }

    content.innerHTML = `
        <div class="item-list">
            ${items.map(item => `
                <div class="item">
                    <div class="item-info">
                        <div class="item-name">${escapeHtml(item.name)}</div>
                    </div>
                    <div class="item-quantity">
                        <span class="qty-value">x${item.quantity}</span>
                    </div>
                </div>
            `).join('')}
        </div>
        <div style="padding: 16px; text-align: center; color: #888; font-size: 13px;">
            🔄 ${__('grocy.bidirectional')}
        </div>
    `;
}

function renderItem(item) {
    const qty = item.quantity || 1;
    const stockHtml = item.stock !== undefined ? ` · ${__('item.stock', {n: item.stock})}` : '';
    return `
        <div class="item" data-name="${escapeHtml(item.name)}">
            <div class="item-check ${item.purchased ? 'checked' : ''}" onclick="togglePurchased('${escapeHtml(item.name)}')"></div>
            <div class="item-info">
                <div class="item-name">${escapeHtml(item.name)}</div>
                ${item.category ? `<div class="item-meta">${escapeHtml(item.category)}${stockHtml}</div>` : (stockHtml ? `<div class="item-meta">${stockHtml}</div>` : '')}
            </div>
            <div class="item-quantity">
                <button class="qty-btn" onclick="changeItemQty('${escapeHtml(item.name)}', -1)">-</button>
                <span class="qty-value">${qty}</span>
                <button class="qty-btn" onclick="changeItemQty('${escapeHtml(item.name)}', 1)">+</button>
            </div>
            <button class="item-delete" onclick="removeItem('${escapeHtml(item.name)}')" title="Entfernen">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        </div>
    `;
}

function renderBAPItem(item) {
    return `
        <div class="item">
            <div class="item-check" onclick="markBAPPurchased('${item.list_id || currentTab}', '${item.id}')"></div>
            <div class="item-info">
                <div class="item-name">${escapeHtml(item.title)}</div>
            </div>
            <div class="item-quantity">
                <span class="qty-value">${item.amount || '1x'}</span>
            </div>
        </div>
    `;
}

// ─── Item Actions ────────────────────────────────────────────

async function togglePurchased(name) {
    const res = await api(`/items/${encodeURIComponent(name)}/purchased`, { method: 'POST' });
    toast(res.result);
    loadItems();
}

async function removeItem(name) {
    if (!confirm( __('item.remove_confirm', {name: name}) )) return;
    const res = await api(`/items/${encodeURIComponent(name)}/remove`, { method: 'POST' });
    loadItems();
    undoToast(res.result, () => api(`/trash/restore/${encodeURIComponent(name)}`, { method: 'POST' }));
}

async function changeItemQty(name, delta) {
    const items = document.querySelectorAll('.item');
    let currentQty = 1;
    items.forEach(el => {
        if (el.dataset.name === name) {
            currentQty = parseInt(el.querySelector('.qty-value').textContent) || 1;
        }
    });
    const newQty = Math.max(1, currentQty + delta);
    await api(`/items/${encodeURIComponent(name)}/quantity`, {
        method: 'POST',
        body: JSON.stringify({ quantity: newQty }),
    });
    loadItems();
}

async function markBAPPurchased(listId, itemId) {
    toast(__('sync.start'));
    loadItems();
}

// ─── Add Item ────────────────────────────────────────────────

function openAddModal() {
    document.getElementById('addModal').classList.add('open');
    document.getElementById('itemName').value = '';
    document.getElementById('itemQuantity').value = '1';
    document.getElementById('itemName').focus();
    loadListOptions();
}

async function loadListOptions() {
    const sel = document.getElementById('itemList');
    sel.innerHTML = '<option value="synced">' + __('add_modal.target_synced') + '</option>';
    try {
        const data = await api('/lists');
        for (const list of (data.lists || [])) {
            sel.innerHTML += `<option value="${list.id}">${list.name}</option>`;
        }
    } catch (e) {}
}

async function addItem() {
    const name = document.getElementById('itemName').value.trim();
    const quantity = parseInt(document.getElementById('itemQuantity').value) || 1;
    const category = document.getElementById('itemCategory').value;
    const listId = document.getElementById('itemList').value;

    if (!name) {
        toast( __('add_modal.name_required') );
        return;
    }

    const res = await api('/items/add', {
        method: 'POST',
        body: JSON.stringify({ name, quantity, category, list_id: listId }),
    });

    toast(res.result || res.error);
    closeModal('addModal');
    loadItems();
}

function changeQuantity(delta) {
    const input = document.getElementById('itemQuantity');
    const current = parseInt(input.value) || 1;
    input.value = Math.max(1, current + delta);
}

// ─── Sync ────────────────────────────────────────────────────

async function syncWithBAP() {
    const btn = document.getElementById('syncBtn');
    const pill = document.getElementById('syncStatus');
    btn.classList.add('syncing');
    if (pill) {
        pill.dataset.status = 'syncing';
        document.getElementById('pillPath').setAttribute('d', 'M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z');
        document.getElementById('pillText').textContent = __('sync.status_syncing');
    }
    toast( __('sync.start') );

    try {
        const res = await api('/sync/full');
        toast(res.result);
        const now = new Date().toISOString();
        localStorage.setItem('grot2buy_last_sync', now);
        lastSyncTime = now;
        updateSyncStatus(true, formatTime(now));
    } catch (e) {
        toast( __('sync.failed') );
        sendNotification(__('notify.sync_error'), __('notify.sync_error_body', { status: e.message }));
        if (led) led.className = 'sync-led sync-led--red';
    } finally {
        btn.classList.remove('syncing');
    }
}

async function pullFromGrocy() {
    toast( __('sync.pull_start') );
    try {
        const res = await api('/sync/grocy/pull');
        toast(res.result);
        await loadItems();
    } catch (e) {
        toast( __('sync.pull_failed') );
        sendNotification(__('notify.sync_error'), __('notify.sync_error_body', { status: e.message }));
    }
}

// ─── Settings ────────────────────────────────────────────────

async function openSettings() {
    document.getElementById('settingsModal').classList.add('open');
    try {
        const data = await api('/config');
        document.getElementById('bapUser').value = data.bap_user || '';
    } catch (e) {}
    const sel = document.getElementById('darkModeSelect');
    if (sel) sel.value = localStorage.getItem('grot2buy_theme') || 'auto';
}

async function saveBAPConfig() {
    const user = document.getElementById('bapUser').value;
    const pass = document.getElementById('bapPass').value;

    const res = await api('/config/bap', {
        method: 'POST',
        body: JSON.stringify({ bap_user: user, bap_pass: pass }),
    });

    toast(res.result);
    closeModal('settingsModal');
    loadLists();
}

async function exportList() {
    const data = await api('/export');
    if (data.export) {
        navigator.clipboard.writeText(data.export);
        toast( __('export.copied', {n: data.count}) );
    }
}

async function clearPurchased() {
    if (!confirm( __('item.clear_confirm') )) return;
    const res = await api('/items/clear-purchased', { method: 'POST' });
    toast(res.result);
    loadItems();
}

// ─── Trash ─────────────────────────────────────────────────────

async function showTrash() {
    const modal = document.getElementById('trashModal');
    modal.classList.add('open');
    document.getElementById('trashList').innerHTML = `<p style="text-align:center;color:#999;">${__('trash.loading')}</p>`;
    try {
        const data = await api('/trash/items');
        const list = document.getElementById('trashList');
        if (!data.items || data.items.length === 0) {
            list.innerHTML = `<p style="text-align:center;color:#999;">${__('trash.empty_hint')}</p>`;
            return;
        }
        list.innerHTML = data.items.map(item => `
            <div class="item trashed-item" data-name="${escapeHtml(item.name)}">
                <div class="item-info">
                    <div class="item-name">${escapeHtml(item.name)}</div>
                    <div class="item-meta">${escapeHtml(item.category)}</div>
                </div>
                <button class="btn-secondary" onclick="restoreFromTrash('${escapeHtml(item.name)}', this)">${__('trash.restore')}</button>
            </div>
        `).join('');
    } catch (e) {
        document.getElementById('trashList').innerHTML = `<p style="text-align:center;color:var(--color-danger);">${e.message}</p>`;
    }
}

function hideTrash() {
    document.getElementById('trashModal').classList.remove('open');
}

async function restoreFromTrash(name, btn) {
    btn.disabled = true;
    btn.textContent = '…';
    const res = await api(`/trash/restore/${encodeURIComponent(name)}`, { method: 'POST' });
    toast(res.result || __('trash.restored'));
    loadItems();
    showTrash();
}

async function emptyTrash() {
    if (!confirm(__('trash.confirm_empty'))) return;
    const res = await api('/trash/empty', { method: 'POST' });
    toast(res.result || __('trash.emptied'));
    loadItems();
    hideTrash();
}

// ─── Language ────────────────────────────────────────────────

async function setLanguage(lang) {
    const res = await api('/config/lang', {
        method: 'POST',
        body: JSON.stringify({ lang }),
    });
    if (res.success) {
        toast( __('lang.changed') );
        setTimeout(() => location.reload(), 1000);
    }
}

// ─── Helpers ─────────────────────────────────────────────────

function openHelp() {
    document.getElementById('helpModal').classList.add('open');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('open');
}

function scrollToTop() {
    document.getElementById('content').scrollTop = 0;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ─── Docs Viewer ─────────────────────────────────────────────

function renderMarkdown(md) {
    const lines = md.split('\n');
    let html = '';
    let inCode = false;
    let codeBuf = [];
    let inList = false;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        if (line.startsWith('```')) {
            if (inCode) {
                html += '<pre><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>\n';
                codeBuf = [];
                inCode = false;
            } else {
                inCode = true;
            }
            continue;
        }
        if (inCode) { codeBuf.push(line); continue; }

        if (line.startsWith('### ')) {
            if (inList) { html += '</ul>\n'; inList = false; }
            html += '<h3>' + escapeHtml(line.slice(4)) + '</h3>\n';
            continue;
        }
        if (line.startsWith('## ')) {
            if (inList) { html += '</ul>\n'; inList = false; }
            html += '<h2>' + escapeHtml(line.slice(3)) + '</h2>\n';
            continue;
        }
        if (line.startsWith('# ')) {
            if (inList) { html += '</ul>\n'; inList = false; }
            html += '<h1>' + escapeHtml(line.slice(2)) + '</h1>\n';
            continue;
        }

        if (line.startsWith('- ') || line.startsWith('* ')) {
            if (!inList) { html += '<ul>\n'; inList = true; }
            html += '<li>' + escapeHtml(line.slice(2)) + '</li>\n';
            continue;
        }

        if (line.match(/^\d+\.\s/)) {
            if (!inList) { html += '<ol>\n'; inList = 'ol'; }
            html += '<li>' + escapeHtml(line.replace(/^\d+\.\s/, '')) + '</li>\n';
            continue;
        }

        if (line.trim() === '') {
            if (inList) { html += '</ul>\n'; inList = false; }
            continue;
        }

        if (line.startsWith('---')) {
            if (inList) { html += '</ul>\n'; inList = false; }
            html += '<hr>\n';
            continue;
        }

        if (inList) { html += '</ul>\n'; inList = false; }
        html += '<p>' + escapeHtml(line) + '</p>\n';
    }
    if (inCode) html += '<pre><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>\n';
    if (inList) html += '</ul>\n';
    return html;
}

async function openDocs(type) {
    try {
        const data = await api('/docs/' + type);
        if (!data || !data.html) throw new Error('empty response');
        document.getElementById('docsModalTitle').textContent = data.title || (type === 'doku' ? __('settings.docs_doku') : __('settings.docs_changelog'));
        document.getElementById('docsBody').innerHTML = data.html;
        document.getElementById('docsModal').classList.add('open');
    } catch (e) {
        console.error('Docs fetch error:', e);
        toast(__('settings.error_load_docs'));
    }
}

// Enter zum Hinzufügen
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && document.getElementById('addModal').classList.contains('open')) {
        if (document.activeElement.id === 'itemName') {
            addItem();
        }
    }
});
