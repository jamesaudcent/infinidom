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
        localStorage.removeItem('infinidom_session_id');
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
     */
    streamInit(path = '/', onOperation, onComplete, onError) {
        const params = new URLSearchParams();
        params.set('path', path);
        
        if (this.sessionId) {
            params.set('session_id', this.sessionId);
        }
        
        return this._streamRequest(`/api/stream/init?${params.toString()}`, onOperation, onComplete, onError);
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
