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

// ─── Init ────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    applyTheme(localStorage.getItem('grot2buy_theme') || 'auto');
    updateDarkModeBtn();
    requestNotificationPermission();
    watchSyncErrors();

    // Parallele API-Calls statt sequentiell — loadItems zeigt sofort Spinner,
    // loadLists blockiert nicht mehr die ganze Seite bei trägem BAP
    await Promise.all([
        loadCategories(),
        loadLists(),
        loadItems(),
    ]);
});

// ─── API Helpers ─────────────────────────────────────────────

async function api(path, opts = {}) {
    const res = await fetch(`${API}${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...opts,
    });
    return res.json();
}

function toast(msg, duration = 3000) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), duration);
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

        let html = '<button class="tab active" data-list="synced" onclick="switchTab(\'synced\', this)">' + __('tab.synced') + '</button>';
        html += '<button class="tab" data-list="grocy" onclick="switchTab(\'grocy\', this)">' + __('tab.grocy') + '</button>';
        for (const list of lists) {
            html += `<button class="tab" data-list="${list.id}" onclick="switchTab('${list.id}', this)">${list.name} (${list.count})</button>`;
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
    content.innerHTML = '<div class="loading"><div class="spinner"></div><p>' + __('loading.data') + '</p></div>';

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
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>' + __('error.load_title') + '</h3><p>' + __('error.load_text') + '</p></div>';
    }
}

function renderSyncedItems(data) {
    const content = document.getElementById('content');
    const byCategory = data.by_category || {};
    const items = data.items || [];

    document.getElementById('itemCount').textContent = items.length;

    if (items.length === 0) {
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🛒</div><h3>' + __('empty.synced_title') + '</h3><p>' + __('empty.synced_text') + '</p></div>';
        return;
    }

    let html = '';
    for (const [cat, catItems] of Object.entries(byCategory)) {
        html += `
            <div class="category">
                <div class="category-header">
                    <span>${getCategoryIcon(cat)}</span>
                    <span>${cat}</span>
                    <span class="category-count">${catItems.length}</span>
                </div>
                <div class="item-list">
                    ${catItems.map(item => renderItem(item)).join('')}
                </div>
            </div>
        `;
    }
    content.innerHTML = html;
}

function renderBAPItems(data) {
    const content = document.getElementById('content');
    const items = data.items || [];

    document.getElementById('itemCount').textContent = items.length;

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

    document.getElementById('itemCount').textContent = items.length;

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
    return `
        <div class="item" data-name="${escapeHtml(item.name)}">
            <div class="item-check ${item.purchased ? 'checked' : ''}" onclick="togglePurchased('${escapeHtml(item.name)}')"></div>
            <div class="item-info">
                <div class="item-name">${escapeHtml(item.name)}</div>
                ${item.category ? `<div class="item-meta">${escapeHtml(item.category)}${item.barcode ? ' · ' + escapeHtml(item.barcode) : ''}</div>` : ''}
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
    toast(res.result);
    loadItems();
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
    btn.classList.add('syncing');
    toast( __('sync.start') );

    try {
        const res = await api('/sync/full');
        toast(res.result);
        await loadLists();
        await loadItems();
    } catch (e) {
        toast( __('sync.failed') );
        sendNotification(__('notify.sync_error'), __('notify.sync_error_body', { status: e.message }));
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
        document.getElementById('syncInterval').value = data.sync_interval ?? 5;
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

async function saveSyncInterval() {
    const interval = parseInt(document.getElementById('syncInterval').value) || 0;
    const res = await api('/config/sync-interval', {
        method: 'POST',
        body: JSON.stringify({ interval }),
    });
    toast(res.result);
    closeModal('settingsModal');
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

function getCategoryIcon(cat) {
    const icons = {
        'Obst & Gemüse': '🥬',
        'Milchprodukte': '🥛',
        'Fleisch & Wurst': '🥩',
        'Getränke': '🥤',
        'Brot & Gebäck': '🍞',
        'Vorrat': '🥫',
        'Tiefkühl': '❄️',
        'Süßigkeiten': '🍫',
        'Drogerie': '🧴',
        'Sonstiges': '📦',
    };
    return icons[cat] || '📦';
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Enter zum Hinzufügen
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && document.getElementById('addModal').classList.contains('open')) {
        if (document.activeElement.id === 'itemName') {
            addItem();
        }
    }
});
