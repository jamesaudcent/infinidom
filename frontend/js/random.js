/**
 * infinidom Framework - Main Entry Point
 * 
 * Initializes the framework, sets up event capture, and coordinates
 * between the API client and DOM patcher via streaming.
 */

class Infinidom {
    constructor(options = {}) {
        this.options = {
            container: '#app',
            apiBaseUrl: '',
            debug: false,
            ...options,
        };
        
        this.apiClient = new InfinidomAPIClient(this.options.apiBaseUrl);
        this.domPatcher = new InfinidomDOMPatcher();
        this.isLoading = false;
        this.initialized = false;
        
        this.log('infinidom Framework initializing...');
    }
    
    /**
     * Debug logging
     */
    log(...args) {
        if (this.options.debug) {
            console.log('[infinidom]', ...args);
        }
    }
    
    /**
     * Performance timing helper
     */
    startTiming(label) {
        this._timings = this._timings || {};
        this._timings[label] = performance.now();
    }
    
    endTiming(label) {
        if (!this._timings || !this._timings[label]) return null;
        const duration = performance.now() - this._timings[label];
        delete this._timings[label];
        return duration;
    }
    
    logTiming(label, duration, extra = '') {
        const formatted = duration.toFixed(0);
        console.log(`⏱️ [infinidom] ${label}: ${formatted}ms ${extra}`);
        
        // Store for analysis
        this._performanceLog = this._performanceLog || [];
        this._performanceLog.push({ label, duration, timestamp: Date.now(), extra });
    }
    
    /**
     * Get performance summary
     */
    getPerformanceSummary() {
        if (!this._performanceLog || this._performanceLog.length === 0) {
            return 'No performance data collected';
        }
        
        const byLabel = {};
        this._performanceLog.forEach(entry => {
            if (!byLabel[entry.label]) byLabel[entry.label] = [];
            byLabel[entry.label].push(entry.duration);
        });
        
        const summary = {};
        for (const [label, durations] of Object.entries(byLabel)) {
            const avg = durations.reduce((a, b) => a + b, 0) / durations.length;
            const min = Math.min(...durations);
            const max = Math.max(...durations);
            summary[label] = { count: durations.length, avg: avg.toFixed(0), min: min.toFixed(0), max: max.toFixed(0) };
        }
        
        console.table(summary);
        return summary;
    }
    
    /**
     * Initialize the framework
     */
    async init() {
        try {
            // Set up container
            const container = document.querySelector(this.options.container);
            if (!container) {
                throw new Error(`Container not found: ${this.options.container}`);
            }
            
            // Wait for Snabbdom to be ready
            await this.domPatcher.ensureReady();
            this.domPatcher.setContainer(container);
            
            // Set up global event delegation
            this.setupEventDelegation();
            
            // Request initial page content via streaming
            await this.loadInitialContent();
            
            this.initialized = true;
            this.log('Framework initialized successfully');
            
        } catch (error) {
            console.error('infinidom initialization failed:', error);
            this.showError(error.message);
        }
    }
    
    /**
     * Load initial content via streaming
     */
    async loadInitialContent() {
        const path = window.location.pathname;
        this.log('Loading initial content (streaming) for path:', path);
        
        // Start timing
        this.startTiming('total');
        this.startTiming('firstOp');
        let firstOpReceived = false;
        let opCount = 0;
        
        return new Promise((resolve, reject) => {
            this.apiClient.streamInit(
                path,
                // onOperation
                (operation) => {
                    if (!firstOpReceived) {
                        const firstOpTime = this.endTiming('firstOp');
                        this.logTiming('Streaming - First Operation', firstOpTime, `(${path})`);
                        firstOpReceived = true;
                        // Hide loading after first operation (content is appearing)
                        this.setLoading(false);
                    }
                    
                    opCount++;
                    this.log(`Operation ${opCount}:`, operation);
                    
                    const result = this.domPatcher.applyOperation(operation, this.handleEvent.bind(this));
                    
                    // Handle meta operation for URL update
                    if (result && result.path && result.path !== window.location.pathname) {
                        history.pushState({ path: result.path }, '', result.path);
                        this.log('Updated URL to:', result.path);
                    }
                },
                // onComplete
                () => {
                    const totalTime = this.endTiming('total');
                    this.logTiming('Streaming - TOTAL', totalTime, `(${path}, ${opCount} ops)`);
                    resolve();
                },
                // onError
                (error) => {
                    console.error('Streaming error:', error);
                    this.showError('Failed to load page. Please check if the server is running.');
                    reject(error);
                }
            );
        });
    }
    
    /**
     * Set up event delegation for capturing user interactions
     */
    setupEventDelegation() {
        // Click events - delegated to document
        document.addEventListener('click', (e) => {
            // Check for explicitly marked interactive elements
            let target = e.target.closest('[data-infinidom-interactive="true"]');
            
            // Also capture clicks on links and buttons (implicit interactive elements)
            if (!target) {
                target = e.target.closest('a, button');
            }
            
            if (target) {
                // Skip external links - let browser handle them normally
                if (target.tagName === 'A') {
                    const href = target.getAttribute('href');
                    // External link conditions:
                    // - Has target="_blank"
                    // - Starts with http:// or https:// and different origin
                    // - Starts with mailto:, tel:, etc.
                    if (target.getAttribute('target') === '_blank') {
                        return; // Let browser handle external link
                    }
                    if (href && (href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('javascript:'))) {
                        return; // Let browser handle special protocols
                    }
                    if (href && (href.startsWith('http://') || href.startsWith('https://'))) {
                        try {
                            const url = new URL(href);
                            if (url.origin !== window.location.origin) {
                                return; // Let browser handle external link
                            }
                        } catch (e) {
                            // Invalid URL, let browser handle it
                            return;
                        }
                    }
                }
                
                e.preventDefault();
                e.stopPropagation();
                this.handleEvent(e, 'click', target);
            }
        }, true);
        
        // Form submissions
        document.addEventListener('submit', (e) => {
            e.preventDefault();
            const form = e.target.closest('form');
            if (form) {
                this.handleEvent(e, 'submit', form);
            }
        }, true);
        
        // Input changes for interactive inputs
        document.addEventListener('change', (e) => {
            const target = e.target.closest('input, select, textarea');
            if (target) {
                this.handleEvent(e, 'change', target);
            }
        }, true);
        
        // Handle browser back/forward - use cache if available
        window.addEventListener('popstate', (event) => {
            const path = window.location.pathname;
            
            // Check frontend cache first for instant back/forward
            if (this.apiClient.hasPageCached(path)) {
                this.log(`📦 Back/Forward to ${path} - serving from cache`);
                const cachedOps = this.apiClient.getCachedPage(path);
                
                // Notify backend
                this.apiClient.notifyNavigation(path);
                
                // Replay operations
                for (const operation of cachedOps) {
                    this.domPatcher.applyOperation(operation, this.handleEvent.bind(this));
                }
            } else {
                // Not in cache, fetch from server
                this.loadInitialContent();
            }
        });
        
        this.log('Event delegation set up');
    }
    
    /**
     * Handle a user interaction event
     */
    async handleEvent(event, eventType, targetElement = null) {
        if (this.isLoading) {
            this.log('Ignoring event while loading');
            return;
        }
        
        const target = targetElement || event.target;
        
        // Build event data to send to backend
        const eventData = this.buildEventData(event, eventType, target);
        this.log('Handling event:', eventData);
        
        // Check for data-path attribute on buttons (explicit navigation target)
        const dataPath = target.getAttribute('data-path');
        
        // Determine interaction type for timing labels
        const isNavigation = (target.tagName?.toLowerCase() === 'a' && target.href) || dataPath;
        const interactionType = isNavigation ? 'Navigation' : `${eventType} (${target.tagName?.toLowerCase() || 'unknown'})`;
        const targetInfo = eventData.target_text?.substring(0, 20) || eventData.target_id || target.tagName;
        
        // Extract navigation path from links or data-path attribute
        let navigationPath = null;
        
        // First check for explicit data-path attribute (buttons with known destinations)
        if (dataPath) {
            navigationPath = dataPath.startsWith('/') ? dataPath : '/' + dataPath;
            this.log('Navigation path from data-path:', navigationPath);
        }
        // Then check for href on links
        else if (target.tagName?.toLowerCase() === 'a' && target.href) {
            try {
                const url = new URL(target.href, window.location.origin);
                // Only handle internal navigation (same origin)
                if (url.origin === window.location.origin) {
                    navigationPath = url.pathname;
                }
            } catch (e) {
                // If href is just a path like "/about", use it directly
                const href = target.getAttribute('href');
                if (href && href.startsWith('/')) {
                    navigationPath = href;
                }
            }
        }
        
        await this.handleEventStreaming(eventData, interactionType, targetInfo, navigationPath);
    }
    
    /**
     * Handle event with streaming DOM operations
     */
    async handleEventStreaming(eventData, interactionType, targetInfo, navigationPath) {
        this.log('Handling event (streaming):', eventData);
        
        // Check if this is a navigation to a cached page
        if (navigationPath && this.apiClient.hasPageCached(navigationPath)) {
            this.log(`📦 Serving ${navigationPath} from local cache`);
            
            // Get cached operations
            const cachedOps = this.apiClient.getCachedPage(navigationPath);
            
            // Notify backend to keep conversation in sync
            this.apiClient.notifyNavigation(navigationPath);
            
            // Apply cached operations
            let opCount = 0;
            for (const operation of cachedOps) {
                opCount++;
                const result = this.domPatcher.applyOperation(operation, this.handleEvent.bind(this));
                
                // Handle URL update
                if (result && result.path && result.path !== window.location.pathname) {
                    history.pushState({ path: result.path }, '', result.path);
                    this.log('Updated URL to:', result.path);
                }
            }
            
            this.logTiming(`${interactionType} (cached)`, 0, `(${targetInfo}, ${opCount} ops from cache)`);
            return;
        }
        
        // Start timing
        this.startTiming('total');
        this.startTiming('firstOp');
        let firstOpReceived = false;
        let opCount = 0;
        const operations = [];  // Collect for caching
        let actualPath = navigationPath;  // May be updated from meta operation
        
        // Don't show full loading overlay for streaming - content appears progressively
        this.isLoading = true;
        
        return new Promise((resolve) => {
            this.apiClient.streamInteract(
                eventData,
                // onOperation
                (operation) => {
                    if (!firstOpReceived) {
                        const firstOpTime = this.endTiming('firstOp');
                        this.logTiming(`${interactionType} (streaming) - First Op`, firstOpTime, `(${targetInfo})`);
                        firstOpReceived = true;
                    }
                    
                    opCount++;
                    operations.push(operation);
                    
                    const result = this.domPatcher.applyOperation(operation, this.handleEvent.bind(this));
                    
                    // Handle meta operation for URL update and path tracking
                    if (result && result.path) {
                        actualPath = result.path;
                        if (actualPath && actualPath !== window.location.pathname) {
                            history.pushState({ path: actualPath }, '', actualPath);
                            this.log('Updated URL to:', actualPath);
                        }
                    }
                },
                // onComplete
                () => {
                    const totalTime = this.endTiming('total');
                    this.logTiming(`${interactionType} (streaming) - TOTAL`, totalTime, `(${targetInfo}, ${opCount} ops)`);
                    
                    // Cache the result using the actual path from the response
                    if (actualPath && operations.length > 0) {
                        this.apiClient.cachePage(actualPath, operations);
                        this.log(`💾 Cached ${actualPath} (${operations.length} operations)`);
                    }
                    
                    this.isLoading = false;
                    resolve();
                },
                // onError
                (error) => {
                    console.error('Streaming interaction failed:', error);
                    this.isLoading = false;
                    resolve();
                }
            );
        });
    }
    
    /**
     * Build event data object from DOM event
     */
    buildEventData(event, eventType, target) {
        const data = {
            event_type: eventType,
            target_tag: target.tagName?.toLowerCase(),
            target_text: target.textContent?.trim().substring(0, 100),
            target_id: target.id || null,
            target_classes: target.className ? target.className.split(' ').filter(c => c) : [],
        };
        
        // Add href for links
        if (target.href) {
            data.href = target.href;
        }
        
        // Add path for navigation buttons
        const dataPath = target.getAttribute('data-path');
        if (dataPath) {
            data.path = dataPath.startsWith('/') ? dataPath : '/' + dataPath;
        }
        
        // Add value for inputs
        if (target.value !== undefined) {
            data.input_value = target.value;
        }
        
        // Collect data attributes
        const dataAttrs = {};
        for (const attr of target.attributes || []) {
            if (attr.name.startsWith('data-')) {
                const key = attr.name.replace('data-', '').replace(/-/g, '_');
                dataAttrs[key] = attr.value;
            }
        }
        if (Object.keys(dataAttrs).length > 0) {
            data.data_attributes = dataAttrs;
        }
        
        // Build CSS selector for targeting
        let selector = target.tagName?.toLowerCase();
        if (target.id) {
            selector = `#${target.id}`;
        } else if (target.className) {
            selector += '.' + target.className.split(' ').filter(c => c).join('.');
        }
        data.target_selector = selector;
        
        // For forms, collect all form data
        if (eventType === 'submit' && target.tagName === 'FORM') {
            const formData = new FormData(target);
            data.extra = {
                form_data: Object.fromEntries(formData.entries()),
            };
        }
        
        // Build DOM hierarchy context (from clicked element up to body)
        data.element_hierarchy = this.buildElementHierarchy(target);
        
        return data;
    }
    
    /**
     * Build the DOM hierarchy from an element up to body for context
     * This helps the AI understand what a generic "Learn More" button relates to
     */
    buildElementHierarchy(element) {
        const hierarchy = [];
        let current = element;
        const maxDepth = 10; // Limit depth to avoid massive payloads
        let depth = 0;
        
        while (current && current !== document.body && depth < maxDepth) {
            const nodeInfo = this.extractNodeInfo(current);
            if (nodeInfo) {
                hierarchy.push(nodeInfo);
            }
            current = current.parentElement;
            depth++;
        }
        
        return hierarchy;
    }
    
    /**
     * Extract relevant information from a DOM node for context
     */
    extractNodeInfo(element) {
        if (!element || !element.tagName) return null;
        
        const tag = element.tagName.toLowerCase();
        const info = { tag };
        
        // Add ID if present
        if (element.id) {
            info.id = element.id;
        }
        
        // Add meaningful classes (filter out utility classes)
        if (element.className && typeof element.className === 'string') {
            const classes = element.className.split(' ').filter(c => c && !this.isUtilityClass(c));
            if (classes.length > 0) {
                info.classes = classes;
            }
        }
        
        // Add data attributes (often contain semantic meaning)
        const dataAttrs = {};
        for (const attr of element.attributes || []) {
            if (attr.name.startsWith('data-') && !attr.name.includes('infinidom')) {
                const key = attr.name.replace('data-', '').replace(/-/g, '_');
                dataAttrs[key] = attr.value;
            }
        }
        if (Object.keys(dataAttrs).length > 0) {
            info.data = dataAttrs;
        }
        
        // Add role attribute if present (accessibility/semantic info)
        if (element.getAttribute('role')) {
            info.role = element.getAttribute('role');
        }
        
        // Add aria-label if present (often contains descriptive text)
        if (element.getAttribute('aria-label')) {
            info.aria_label = element.getAttribute('aria-label');
        }
        
        // For semantic elements, extract key text content
        const textContent = this.extractContextualText(element, tag);
        if (textContent) {
            info.text = textContent;
        }
        
        return info;
    }
    
    /**
     * Extract meaningful text content from an element based on its type
     */
    extractContextualText(element, tag) {
        // For headings, get the full text
        if (['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(tag)) {
            return element.textContent?.trim().substring(0, 150) || null;
        }
        
        // For labeled containers, check for heading children
        if (['section', 'article', 'aside', 'nav', 'main', 'header', 'footer', 'div', 'figure'].includes(tag)) {
            // Look for a heading child that labels this section
            const heading = element.querySelector('h1, h2, h3, h4, h5, h6');
            if (heading) {
                return heading.textContent?.trim().substring(0, 150) || null;
            }
            
            // Check for figcaption
            if (tag === 'figure') {
                const caption = element.querySelector('figcaption');
                if (caption) {
                    return caption.textContent?.trim().substring(0, 150) || null;
                }
            }
            
            // Check for legend in fieldsets
            const legend = element.querySelector('legend');
            if (legend) {
                return legend.textContent?.trim().substring(0, 150) || null;
            }
        }
        
        // For list items, get direct text (not nested lists)
        if (tag === 'li') {
            // Get text nodes directly inside the li, not from nested elements
            const directText = Array.from(element.childNodes)
                .filter(node => node.nodeType === Node.TEXT_NODE)
                .map(node => node.textContent.trim())
                .filter(text => text)
                .join(' ');
            if (directText) {
                return directText.substring(0, 100);
            }
        }
        
        // For table cells, get the cell content and header context
        if (tag === 'td' || tag === 'th') {
            return element.textContent?.trim().substring(0, 100) || null;
        }
        
        // For table rows, summarize the row
        if (tag === 'tr') {
            const cells = Array.from(element.querySelectorAll('td, th'))
                .slice(0, 3) // First 3 cells for context
                .map(cell => cell.textContent?.trim())
                .filter(text => text)
                .join(' | ');
            return cells ? cells.substring(0, 150) : null;
        }
        
        // For labels, get the label text
        if (tag === 'label') {
            return element.textContent?.trim().substring(0, 100) || null;
        }
        
        return null;
    }
    
    /**
     * Check if a class name is likely a utility/layout class vs semantic
     */
    isUtilityClass(className) {
        // Common utility class patterns to filter out
        const utilityPatterns = [
            /^(m|p|mx|my|mt|mb|ml|mr|px|py|pt|pb|pl|pr)-\d/, // spacing
            /^(w|h|min-w|min-h|max-w|max-h)-/, // sizing
            /^(flex|grid|block|inline|hidden)$/, // display
            /^(justify|items|content|self)-/, // flex/grid alignment
            /^(gap|space)-/, // spacing
            /^(text|font|leading|tracking)-/, // typography utilities
            /^(bg|border|rounded|shadow)-/, // visual utilities
            /^(absolute|relative|fixed|sticky)$/, // positioning
            /^(top|right|bottom|left|inset)-/, // positioning values
            /^(z|opacity|overflow|cursor)-/, // misc utilities
            /^(col|row)-span-/, // grid spans
            /^(sm|md|lg|xl|2xl):/, // responsive prefixes
            /^(hover|focus|active|disabled):/, // state prefixes
        ];
        
        return utilityPatterns.some(pattern => pattern.test(className));
    }
    
    /**
     * Set loading state
     */
    setLoading(loading) {
        this.isLoading = loading;
        
        if (loading) {
            this.domPatcher.showLoading();
        } else {
            this.domPatcher.hideLoading();
        }
    }
    
    /**
     * Show error message to user
     */
    showError(message) {
        const container = document.querySelector(this.options.container);
        if (container) {
            container.innerHTML = `
                <div class="infinidom-loading">
                    <div class="infinidom-error">
                        <h2>∞ infinidom Error</h2>
                        <p>${message}</p>
                        <button onclick="window.location.reload()">Retry</button>
                    </div>
                </div>
            `;
        }
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Create global instance
    window.infinidom = new Infinidom({
        container: '#app',
        debug: true,
    });
    
    // Initialize the framework
    window.infinidom.init();
});

// Export for manual initialization
window.Infinidom = Infinidom;
