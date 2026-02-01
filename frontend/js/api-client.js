/**
 * infinidom Framework - API Client
 * 
 * HTTP client for communicating with the infinidom backend.
 * Handles request/response formatting and session management via streaming.
 */

class InfinidomAPIClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
        this.sessionId = this.loadSessionId();
        this.pageCache = new Map();  // Frontend page cache: path -> {operations, timestamp}
    }
    
    /**
     * Load session ID from localStorage
     */
    loadSessionId() {
        return localStorage.getItem('infinidom_session_id') || null;
    }
    
    /**
     * Save session ID to localStorage
     */
    saveSessionId(sessionId) {
        this.sessionId = sessionId;
        localStorage.setItem('infinidom_session_id', sessionId);
    }
    
    /**
     * Clear session (for logout or reset)
     */
    clearSession() {
        this.sessionId = null;
        this.pageCache.clear();
        localStorage.removeItem('infinidom_session_id');
    }
    
    /**
     * Check if a page is cached locally
     */
    hasPageCached(path) {
        return this.pageCache.has(path);
    }
    
    /**
     * Get cached page operations
     */
    getCachedPage(path) {
        const cached = this.pageCache.get(path);
        return cached ? cached.operations : null;
    }
    
    /**
     * Cache page operations locally
     */
    cachePage(path, operations) {
        this.pageCache.set(path, {
            operations: operations,
            timestamp: Date.now()
        });
    }
    
    /**
     * Notify backend of navigation to cached page
     * Keeps conversation context in sync
     */
    async notifyNavigation(path) {
        if (!this.sessionId) return;
        
        try {
            await fetch(`${this.baseUrl}/api/notify/navigation`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    path: path
                })
            });
        } catch (error) {
            console.warn('Failed to notify navigation:', error);
        }
    }
    
    /**
     * Make an API request
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };
        
        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers,
            },
        };
        
        try {
            const response = await fetch(url, mergedOptions);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP error ${response.status}`);
            }
            
            const data = await response.json();
            
            // Save session ID if present in response
            if (data.session_id) {
                this.saveSessionId(data.session_id);
            }
            
            return data;
        } catch (error) {
            console.error('infinidom API Error:', error);
            throw error;
        }
    }
    
    /**
     * Health check
     */
    async health() {
        return this.request('/api/health');
    }
    
    /**
     * Get server configuration
     */
    async getConfig() {
        return this.request('/api/config');
    }
    
    /**
     * Stream initial page load via SSE
     * @param {string} path - The path to load
     * @param {function} onOperation - Callback for each operation received
     * @param {function} onComplete - Callback when stream completes
     * @param {function} onError - Callback for errors
     * @param {boolean} skipLocalCache - If true, skip local cache and fetch from server
     */
    streamInit(path = '/', onOperation, onComplete, onError, skipLocalCache = false) {
        // Check local cache first (performance optimization)
        if (!skipLocalCache && this.hasPageCached(path)) {
            const cachedOps = this.getCachedPage(path);
            console.log(`📦 Serving ${path} from local cache`);
            
            // Notify backend so conversation stays in sync
            this.notifyNavigation(path);
            
            // Replay cached operations
            setTimeout(() => {
                for (const op of cachedOps) {
                    if (onOperation) onOperation(op);
                }
                if (onComplete) onComplete();
            }, 0);
            
            return () => {}; // No-op close function
        }
        
        const params = new URLSearchParams();
        params.set('path', path);
        
        if (this.sessionId) {
            params.set('session_id', this.sessionId);
        }
        
        // Collect operations for caching
        const operations = [];
        
        const wrappedOnOperation = (op) => {
            operations.push(op);
            if (onOperation) onOperation(op);
        };
        
        const wrappedOnComplete = () => {
            // Cache the page locally
            if (operations.length > 0) {
                this.cachePage(path, operations);
                console.log(`💾 Cached ${path} (${operations.length} operations)`);
            }
            if (onComplete) onComplete();
        };
        
        return this._streamRequest(`/api/stream/init?${params.toString()}`, wrappedOnOperation, wrappedOnComplete, onError);
    }
    
    /**
     * Stream interaction response via SSE
     * @param {object} event - The event data
     * @param {function} onOperation - Callback for each operation received
     * @param {function} onComplete - Callback when stream completes
     * @param {function} onError - Callback for errors
     */
    async streamInteract(event, onOperation, onComplete, onError) {
        const payload = {
            session_id: this.sessionId,
            event: event,
            current_url: window.location.pathname,
            viewport: {
                width: window.innerWidth,
                height: window.innerHeight,
            },
            current_dom: document.body.innerHTML,
        };
        
        // For POST requests with SSE, we need to use fetch and handle the stream
        try {
            const response = await fetch(`${this.baseUrl}/api/stream/interact`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) {
                    break;
                }
                
                buffer += decoder.decode(value, { stream: true });
                
                // Process complete SSE messages
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line in buffer
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            
                            if (data.type === 'session') {
                                this.saveSessionId(data.session_id);
                            } else if (data.type === 'complete') {
                                if (onComplete) onComplete();
                            } else if (data.type === 'error') {
                                if (onError) onError(new Error(data.error));
                            } else {
                                if (onOperation) onOperation(data);
                            }
                        } catch (e) {
                            console.warn('Failed to parse SSE data:', line);
                        }
                    }
                }
            }
        } catch (error) {
            if (onError) onError(error);
        }
    }
    
    /**
     * Internal method to handle SSE streaming for GET requests
     */
    _streamRequest(endpoint, onOperation, onComplete, onError) {
        const url = `${this.baseUrl}${endpoint}`;
        const eventSource = new EventSource(url);
        
        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === 'session') {
                    this.saveSessionId(data.session_id);
                } else if (data.type === 'cached') {
                    // Backend is serving from its cache
                    console.log(`📦 Backend serving ${data.path} from cache`);
                } else if (data.type === 'complete') {
                    eventSource.close();
                    if (onComplete) onComplete();
                } else if (data.type === 'error') {
                    eventSource.close();
                    if (onError) onError(new Error(data.error));
                } else {
                    if (onOperation) onOperation(data);
                }
            } catch (e) {
                console.warn('Failed to parse SSE message:', event.data);
            }
        };
        
        eventSource.onerror = (error) => {
            eventSource.close();
            if (onError) onError(error);
        };
        
        // Return a function to close the connection
        return () => eventSource.close();
    }
}

// Export for use in other modules
window.InfinidomAPIClient = InfinidomAPIClient;
