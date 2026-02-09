/**
 * Complete Offline-First Sync Engine for ELP Relatórios
 * Handles bidirectional sync between IndexedDB and PostgreSQL
 */

class SyncEngine {
    constructor() {
        this.isSyncing = false;
        this.lastSyncTime = null;
        this.syncInterval = null;
    }

    /**
     * Initialize sync engine - start periodic sync
     */
    async init() {
        // PERMISSION CHECK: Do not sync if not logged in
        if (!localStorage.getItem('token')) {
            console.log('🚫 No auth token found. Sync engine paused.');
            return;
        }

        // Load last sync time
        this.lastSyncTime = await db.metadata.getItem('last_sync_time');

        // Sync on app start if online
        if (navigator.onLine) {
            await this.fullSync();
        }

        // Setup periodic sync every 5 minutes when online
        this.syncInterval = setInterval(async () => {
            if (navigator.onLine && !this.isSyncing) {
                await this.fullSync();
            }
        }, 5 * 60 * 1000); // 5 minutes

        // Sync when coming back online
        window.addEventListener('online', async () => {
            console.log('📶 Connection restored - starting sync...');
            await this.fullSync();
        });
    }

    /**
     * Full bidirectional sync
     */
    async fullSync() {
        if (this.isSyncing) {
            console.log('⏳ Sync already in progress...');
            return;
        }

        this.isSyncing = true;
        console.log('🔄 Starting full sync...');

        try {
            // Step 1: Push local changes to server
            await this.pushLocalChanges();

            // Step 2: Pull server data to local
            await this.pullServerData();

            // Update last sync time
            this.lastSyncTime = new Date().toISOString();
            await db.metadata.setItem('last_sync_time', this.lastSyncTime);

            console.log('✅ Sync completed successfully!');
            this.showSyncNotification('Sincronização concluída');

        } catch (error) {
            console.error('❌ Sync failed:', error);
            this.showSyncNotification('Erro na sincronização', 'error');
        } finally {
            this.isSyncing = false;
        }
    }

    /**
     * Push local changes to server
     */
    async pushLocalChanges() {
        console.log('📤 Pushing local changes to server...');

        // Get pending queue
        const queue = JSON.parse(localStorage.getItem('request_queue') || '[]');

        if (queue.length === 0) {
            console.log('✓ No pending changes to push');
            return;
        }

        console.log(`📤 Pushing ${queue.length} pending changes...`);

        const processed = [];
        const failed = [];

        for (const item of queue) {
            try {
                await api.request(item.endpoint, item.options);
                processed.push(item.id);
                console.log(`✓ Pushed: ${item.endpoint}`);
            } catch (error) {
                console.error(`✗ Failed to push: ${item.endpoint}`, error);
                failed.push(item);
            }
        }

        // Remove processed items
        const remaining = queue.filter(item => !processed.includes(item.id));
        localStorage.setItem('request_queue', JSON.stringify(remaining));

        console.log(`✅ Pushed ${processed.length} changes, ${failed.length} failed`);
    }

    /**
     * Pull server data to local storage
     */
    async pullServerData() {
        console.log('📥 Pulling data from server...');

        try {
            // Pull all data using sync endpoint
            const data = await api.get('/sync/down');

            // Store projects
            if (data.projetos) {
                await db.projects.setItem('all', data.projetos);
                console.log(`✓ Synced ${data.projetos.length} projects`);
            }

            // Store reports
            if (data.relatorios) {
                await db.reports.setItem('all', data.relatorios);
                console.log(`✓ Synced ${data.relatorios.length} reports`);
            }

            // Store visits
            if (data.visitas) {
                await db.visits.setItem('all', data.visitas);
                console.log(`✓ Synced ${data.visitas.length} visits`);
            }

            console.log('✅ All data pulled successfully');

        } catch (error) {
            console.error('❌ Failed to pull server data:', error);

            // Should prompt user if server is truly down
            if (error.message.includes('500') || error.message.includes('503')) {
                this.showSyncNotification('Falha no Servidor. Tente mais tarde.', 'error');
            } else if (!navigator.onLine) {
                // Silent fail for offline
            } else {
                this.showSyncNotification('Erro ao sincronizar dados', 'error');
            }
            throw error;
        }
    }

    /**
     * Save data locally and queue for sync
     */
    async saveLocally(type, data, endpoint, method = 'POST') {
        console.log(`💾 Saving ${type} locally...`);

        // Generate local ID if needed
        if (!data.id) {
            data.id = 'local_' + Date.now();
            data._isLocal = true;
        }

        // Save to IndexedDB
        const storeName = type + 's'; // projects, reports, visits
        const existing = await db[storeName].getItem('all') || [];

        // Check if updating existing item
        const index = existing.findIndex(item => item.id === data.id);
        if (index >= 0) {
            existing[index] = data;
        } else {
            existing.push(data);
        }

        await db[storeName].setItem('all', existing);
        console.log(`✓ Saved ${type} locally`);

        // Queue for server sync
        if (navigator.onLine) {
            try {
                // Try to sync immediately
                const response = await api.request(endpoint, {
                    method,
                    body: JSON.stringify(data)
                });

                // Update local data with server ID
                if (response.id && data._isLocal) {
                    data.id = response.id;
                    delete data._isLocal;
                    await db[storeName].setItem('all', existing);
                }

                console.log(`✓ Synced ${type} to server immediately`);
            } catch (error) {
                console.warn(`⚠ Failed to sync immediately, will retry later:`, error);
                // Already queued by api.request
            }
        } else {
            console.log(`📴 Offline - ${type} will sync when online`);
        }

        return data;
    }

    /**
     * Show sync notification to user
     */
    showSyncNotification(message, type = 'success') {
        // Create toast notification
        const toast = document.createElement('div');
        toast.className = `sync-toast ${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: ${type === 'error' ? '#dc3545' : '#28a745'};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    /**
     * Get sync status
     */
    getSyncStatus() {
        const pendingCount = api.getPendingCount();
        return {
            isSyncing: this.isSyncing,
            lastSyncTime: this.lastSyncTime,
            pendingChanges: pendingCount,
            isOnline: navigator.onLine
        };
    }

    /**
     * Manual sync trigger
     */
    async manualSync() {
        console.log('🔄 Manual sync triggered');
        await this.fullSync();
    }
}

// Create global instance
window.syncEngine = new SyncEngine();

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        syncEngine.init();
    });
} else {
    syncEngine.init();
}
