/**
 * API Client for ELP Relatórios
 * Handles all communication with https://elpconsultoria.pro/api
 * Supports offline mode with request queuing
 */

class APIClient {
    constructor() {
        this.baseURL = 'https://web-production-20dbc.up.railway.app/api';
        this.token = localStorage.getItem('token');
        this.isOnline = navigator.onLine;

        // Monitor network status
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.processPendingRequests();
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
        });
    }

    /**
     * Make authenticated API request
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;

        // Ensure headers exist
        options.headers = options.headers || {};

        // Add Authorization if token exists
        if (this.token) {
            options.headers['Authorization'] = `Bearer ${this.token}`;
        }

        // Default to JSON content type unless it's FormData
        if (!(options.body instanceof FormData)) {
            options.headers['Content-Type'] = 'application/json';
        }

        console.log(`[API] Requesting: ${endpoint}`, options);

        if (!navigator.onLine) {
            console.warn('[API] Offline mode detected. Queueing request.');
            this.queueRequest(endpoint, options);
            throw new Error('Offline: Request queued');
        }

        try {
            const response = await fetch(url, options);
            console.log(`[API] Response status: ${response.status}`);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('[API] Error response:', errorText);
                try {
                    const errorJson = JSON.parse(errorText);
                    throw new Error(errorJson.message || `HTTP Error ${response.status}`);
                } catch (e) {
                    throw new Error(`HTTP Error ${response.status}: ${errorText}`);
                }
            }

            // Handle empty responses (like 204 No Content)
            if (response.status === 204) return null;

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('[API] Network/Server Error:', error);
            if (navigator.onLine && error.message.includes('Failed to fetch')) {
                console.warn('[API] Fetch failed while online, queuing...');
                this.queueRequest(endpoint, options);
            }
            throw error;
        }
    }

    /**
     * GET request
     */
    async get(endpoint, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'GET'
        });
    }

    /**
     * POST request
     */
    async post(endpoint, data, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * PUT request
     */
    async put(endpoint, data, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETE request
     */
    async delete(endpoint, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'DELETE'
        });
    }

    /**
     * Login and store token
     */
    async login(username, password) {
        const data = await this.post('/login', { username, password });

        if (data.token) {
            this.token = data.token;
            localStorage.setItem('token', data.token);
            localStorage.setItem('user', JSON.stringify(data.user));

            // Cache credentials for offline login
            localStorage.setItem('cached_credentials', btoa(`${username}:${password}`));
        }

        return data;
    }

    /**
     * Offline login using cached credentials
     */
    async offlineLogin(username, password) {
        const cached = localStorage.getItem('cached_credentials');

        if (!cached) {
            throw new Error('Nenhuma credencial em cache. Conecte-se à internet para fazer login.');
        }

        const [cachedUser, cachedPass] = atob(cached).split(':');

        if (cachedUser === username && cachedPass === password) {
            // Use cached user data
            const user = JSON.parse(localStorage.getItem('user') || '{}');
            const token = localStorage.getItem('token');

            return {
                success: true,
                token,
                user,
                offline: true
            };
        } else {
            throw new Error('Credenciais incorretas');
        }
    }

    /**
     * Logout
     */
    logout() {
        this.token = null;
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        // Keep cached credentials for offline login
    }

    /**
     * Handle unauthorized (401) responses
     */
    handleUnauthorized() {
        this.logout();
        window.location.href = 'index.html';
    }

    /**
     * Queue request for later processing
     */
    async queueRequest(endpoint, options) {
        const queue = JSON.parse(localStorage.getItem('request_queue') || '[]');

        queue.push({
            id: Date.now(),
            endpoint,
            options,
            timestamp: new Date().toISOString()
        });

        localStorage.setItem('request_queue', JSON.stringify(queue));
        console.log('Request queued:', endpoint);
    }

    /**
     * Process pending requests when back online
     */
    async processPendingRequests() {
        const queue = JSON.parse(localStorage.getItem('request_queue') || '[]');

        if (queue.length === 0) return;

        console.log(`Processing ${queue.length} pending requests...`);

        const processed = [];
        const failed = [];

        for (const item of queue) {
            try {
                await this.request(item.endpoint, item.options);
                processed.push(item.id);
                console.log('✓ Synced:', item.endpoint);
            } catch (error) {
                console.error('✗ Failed to sync:', item.endpoint, error);
                failed.push(item);
            }
        }

        // Remove processed items
        const remaining = queue.filter(item => !processed.includes(item.id));
        localStorage.setItem('request_queue', JSON.stringify(remaining));

        if (processed.length > 0) {
            console.log(`✓ ${processed.length} requests synced successfully`);
        }

        if (failed.length > 0) {
            console.warn(`⚠ ${failed.length} requests failed to sync`);
        }
    }

    /**
     * Get pending request count
     */
    getPendingCount() {
        const queue = JSON.parse(localStorage.getItem('request_queue') || '[]');
        return queue.length;
    }
}

// Create global instance
window.api = new APIClient();
