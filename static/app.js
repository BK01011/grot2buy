// Grot2Buy — Frontend
const API = '/api';
let currentTab = 'synced';
let categories = [];

// ─── Init ────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    await loadCategories();
    await loadLists();
    await loadItems();
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
        toast(`${filename} heruntergeladen`);
    } catch (e) {
        toast('Download fehlgeschlagen: ' + e.message);
    }
}

// ─── Categories ──────────────────────────────────────────────

async function loadCategories() {
    try {
        const data = await api('/categories');
        categories = data.categories || [];
        const sel = document.getElementById('itemCategory');
        sel.innerHTML = '<option value="">Auto</option>' +
            categories.map(c => `<option value="${c}">${c}</option>`).join('');
    } catch (e) {
        console.error('Kategorien laden fehlgeschlagen:', e);
    }
}

// ─── Lists (Tabs) ───────────────────────────────────────────

async function loadLists() {
    try {
        const data = await api('/lists');
        const tabs = document.getElementById('listTabs');
        const lists = data.lists || [];

        let html = '<button class="tab active" data-list="synced" onclick="switchTab(\'synced\', this)">📋 Synchronisiert</button>';
        html += '<button class="tab" data-list="grocy" onclick="switchTab(\'grocy\', this)">📦 Grocy</button>';
        for (const list of lists) {
            html += `<button class="tab" data-list="${list.id}" onclick="switchTab('${list.id}', this)">${list.name} (${list.count})</button>`;
        }
        tabs.innerHTML = html;
    } catch (e) {
        console.error('Listen laden fehlgeschlagen:', e);
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
    content.innerHTML = '<div class="loading"><div class="spinner"></div><p>Lade Daten...</p></div>';

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
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>Fehler beim Laden</h3><p>Bitte versuche es erneut.</p></div>';
    }
}

function renderSyncedItems(data) {
    const content = document.getElementById('content');
    const byCategory = data.by_category || {};
    const items = data.items || [];

    document.getElementById('itemCount').textContent = items.length;

    if (items.length === 0) {
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🛒</div><h3>Liste ist leer</h3><p>Füge Artikel mit dem + Button hinzu.</p></div>';
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
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📋</div><h3>Liste ist leer</h3></div>';
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
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📦</div><h3>Grocy-Einkaufsliste ist leer</h3></div>';
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
            🔄 Bidirektional: Änderungen werden beim Sync automatisch synchronisiert
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
                ${item.category ? `<div class="item-meta">${item.category}${item.barcode ? ' · ' + item.barcode : ''}</div>` : ''}
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
    if (!confirm(`"${name}" entfernen?`)) return;
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
    const res = await api(`/items/${encodeURIComponent(name)}/quantity`, {
        method: 'POST',
        body: JSON.stringify({ quantity: newQty }),
    });
    loadItems();
}

async function markBAPPurchased(listId, itemId) {
    toast('Wird synchronisiert...');
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
    sel.innerHTML = '<option value="synced">📋 Synchronisiert</option>';
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
        toast('Bitte Namen eingeben');
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
    toast('Synchronisiere...');

    try {
        const res = await api('/sync/full');
        toast(res.result);
        await loadLists();
        await loadItems();
    } catch (e) {
        toast('Sync fehlgeschlagen');
    } finally {
        btn.classList.remove('syncing');
    }
}

async function pullFromGrocy() {
    toast('Hole Artikel aus Grocy...');
    try {
        const res = await api('/sync/grocy/pull');
        toast(res.result);
        await loadItems();
    } catch (e) {
        toast('Fehler beim Holen aus Grocy');
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
        toast(`${data.count} Artikel in die Zwischenablage kopiert`);
    }
}

async function clearPurchased() {
    if (!confirm('Alle erledigten Artikel löschen?')) return;
    const res = await api('/items/clear-purchased', { method: 'POST' });
    toast(res.result);
    loadItems();
}

// ─── Helpers ─────────────────────────────────────────────────

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
