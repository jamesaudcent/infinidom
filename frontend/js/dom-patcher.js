/**
 * infinidom Framework - DOM Patcher
 * 
 * Handles virtual DOM to real DOM patching using Snabbdom.
 * Tracks DOM state and applies updates from the AI.
 * Supports component library for consistent styling.
 */

class InfinidomDOMPatcher {
    constructor() {
        this.currentVNode = null;
        this.container = null;
        this.styleContainer = null;
        this.snabbdom = null;
        this.patch = null;
        this.h = null;
        this.useFallback = true; // Default to fallback until snabbdom loads
        this.components = {}; // Component library definitions
        this.componentsLoaded = false;
        this.initPromise = this.initSnabbdom();
    }
    
    /**
     * Load component library from server
     */
    async loadComponents() {
        if (this.componentsLoaded) return;
        
        try {
            const response = await fetch('/api/ui/components');
            if (response.ok) {
                this.components = await response.json();
                this.componentsLoaded = true;
                console.log('✅ Component library loaded:', Object.keys(this.components).filter(k => !k.startsWith('_')).length, 'components');
            }
        } catch (error) {
            console.warn('Could not load component library:', error);
        }
    }
    
    /**
     * Resolve a component reference to a full DOM node structure
     */
    resolveComponent(node) {
        if (!node || !node.component) return node;
        
        const componentDef = this.components[node.component];
        if (!componentDef) {
            console.warn(`Unknown component: ${node.component}`);
            return node;
        }
        
        // Build the class string from baseClass + variant
        let className = componentDef.baseClass || '';
        
        // Add variant classes
        const variant = node.variant || componentDef.defaultVariant || 'default';
        if (componentDef.variants && componentDef.variants[variant]) {
            className = className ? `${className} ${componentDef.variants[variant]}` : componentDef.variants[variant];
        }
        
        // Add size classes if specified
        if (node.size && componentDef.sizes && componentDef.sizes[node.size]) {
            className = className ? `${className} ${componentDef.sizes[node.size]}` : componentDef.sizes[node.size];
        }
        
        // Add any additional classes from the node
        if (node.class) {
            className = className ? `${className} ${node.class}` : node.class;
        }
        
        // Build the resolved node
        const resolved = {
            tag: componentDef.tag,
            props: {
                attrs: {
                    class: className,
                    ...(node.props?.attrs || {}),
                    ...(node.attrs || {})
                },
                ...(node.props || {})
            },
            children: node.children ? node.children.map(child => this.resolveComponent(child)) : []
        };
        
        // Remove the attrs from props if we moved them
        if (resolved.props.attrs && resolved.props.class) {
            delete resolved.props.class;
        }
        
        return resolved;
    }
    
    /**
     * Recursively resolve all component references in a node tree
     */
    resolveAllComponents(node) {
        if (!node) return node;
        if (typeof node === 'string') return node;
        
        // Resolve this node if it's a component
        const resolved = node.component ? this.resolveComponent(node) : { ...node };
        
        // Recursively resolve children
        if (resolved.children && Array.isArray(resolved.children)) {
            resolved.children = resolved.children.map(child => this.resolveAllComponents(child));
        }
        
        return resolved;
    }
    
    /**
     * Initialize Snabbdom with required modules
     * Handles async loading from ES module
     */
    async initSnabbdom() {
        // Check if snabbdom is already loaded
        if (window.snabbdomReady && window.snabbdom) {
            this._setupSnabbdom(window.snabbdom);
            return;
        }
        
        // Wait for snabbdom to load (max 5 seconds)
        return new Promise((resolve) => {
            const checkSnabbdom = () => {
                if (window.snabbdomReady && window.snabbdom) {
                    this._setupSnabbdom(window.snabbdom);
                    resolve();
                    return true;
                }
                return false;
            };
            
            // Check immediately
            if (checkSnabbdom()) return;
            
            // Listen for the ready event
            window.addEventListener('snabbdom-ready', () => {
                checkSnabbdom();
                resolve();
            }, { once: true });
            
            // Timeout fallback
            setTimeout(() => {
                if (!this.snabbdom) {
                    console.warn('Snabbdom load timeout - using fallback DOM manipulation');
                    this.useFallback = true;
                }
                resolve();
            }, 5000);
        });
    }
    
    /**
     * Set up Snabbdom once it's loaded
     */
    _setupSnabbdom(snabbdomLib) {
        try {
            this.snabbdom = snabbdomLib;
            
            // Create patch function with all modules
            this.patch = snabbdomLib.init([
                snabbdomLib.classModule,
                snabbdomLib.propsModule,
                snabbdomLib.styleModule,
                snabbdomLib.attributesModule,
                snabbdomLib.eventListenersModule,
            ]);
            
            this.h = snabbdomLib.h;
            this.useFallback = false;
            console.log('✅ Snabbdom virtual DOM initialized successfully');
        } catch (error) {
            console.error('Failed to initialize Snabbdom:', error);
            this.useFallback = true;
        }
    }
    
    /**
     * Ensure Snabbdom and components are ready before operations
     */
    async ensureReady() {
        await this.initPromise;
        await this.loadComponents();
    }
    
    /**
     * Set the container element for rendering
     */
    setContainer(element) {
        this.container = element;
        // Create initial vnode from existing element
        this.currentVNode = element;
    }
    
    /**
     * Convert AI response DOM structure to Snabbdom VNode
     * Automatically resolves component references
     */
    toVNode(node, eventHandler) {
        if (typeof node === 'string') {
            return node;
        }
        
        // Resolve component reference if present
        if (node && node.component) {
            node = this.resolveComponent(node);
        }
        
        if (!node || !node.tag) {
            return '';
        }
        
        const data = this.buildVNodeData(node.props || {}, eventHandler);
        const children = (node.children || []).map(child => this.toVNode(child, eventHandler));
        
        return this.h(node.tag, data, children);
    }
    
    /**
     * Build Snabbdom data object from props
     */
    buildVNodeData(props, eventHandler) {
        const data = {};
        
        // Handle attributes
        if (props.attrs) {
            data.attrs = { ...props.attrs };
        }
        
        // Handle classes (can be object or string in attrs)
        if (props.class) {
            data.class = props.class;
        }
        
        // Handle styles
        if (props.style) {
            data.style = props.style;
        }
        
        // Handle props (DOM properties)
        if (props.props) {
            data.props = props.props;
        }
        
        // Handle events - wire up to our event handler
        if (eventHandler) {
            data.on = this.buildEventHandlers(props, eventHandler);
        }
        
        return data;
    }
    
    /**
     * Build event handlers for interactive elements
     */
    buildEventHandlers(props, eventHandler) {
        const handlers = {};
        const attrs = props.attrs || {};
        
        // Check if element is marked as interactive
        const isInteractive = attrs['data-infinidom-interactive'] === 'true' || 
                              attrs['data-infinidom-interactive'] === true;
        
        // Also treat certain elements as interactive by default
        const interactiveTags = ['a', 'button', 'input', 'select', 'textarea'];
        
        if (isInteractive) {
            // Capture click events
            handlers.click = (e) => {
                e.preventDefault();
                e.stopPropagation();
                eventHandler(e, 'click');
            };
        }
        
        // Handle form inputs
        if (attrs.type === 'text' || attrs.type === 'email' || attrs.type === 'password') {
            handlers.change = (e) => eventHandler(e, 'change');
            handlers.input = (e) => eventHandler(e, 'input');
        }
        
        // Handle form submissions
        if (props.attrs && props.attrs['data-infinidom-form'] === 'true') {
            handlers.submit = (e) => {
                e.preventDefault();
                eventHandler(e, 'submit');
            };
        }
        
        return handlers;
    }
    
    /**
     * Apply a DOM response from the AI
     */
    applyResponse(response, eventHandler) {
        if (!response || !response.dom) {
            console.error('Invalid response: missing DOM');
            return false;
        }
        
        try {
            // If using fallback (no Snabbdom), render directly
            if (this.useFallback) {
                return this.applyResponseFallback(response, eventHandler);
            }
            
            // Convert response DOM to VNode
            const newVNode = this.toVNode(response.dom, eventHandler);
            
            // Apply operation based on response
            switch (response.operation) {
                case 'replace':
                    this.replaceContent(newVNode, response.target);
                    break;
                case 'append':
                    this.appendContent(newVNode, response.target);
                    break;
                case 'prepend':
                    this.prependContent(newVNode, response.target);
                    break;
                case 'update':
                    this.updateContent(newVNode, response.target);
                    break;
                default:
                    this.replaceContent(newVNode, response.target);
            }
            
            // Inject styles if provided
            if (response.styles) {
                this.injectStyles(response.styles);
            }
            
            // Update page title if provided
            if (response.meta && response.meta.title) {
                document.title = response.meta.title;
            }
            
            // Execute scripts if provided (with caution)
            if (response.scripts) {
                this.executeScripts(response.scripts);
            }
            
            return true;
        } catch (error) {
            console.error('Error applying DOM response:', error);
            return false;
        }
    }
    
    /**
     * Fallback DOM rendering when Snabbdom is not available
     */
    applyResponseFallback(response, eventHandler) {
        const html = this.vdomToHtml(response.dom);
        const target = response.target === 'body' ? document.body : 
                       document.querySelector(response.target) || document.getElementById('app');
        
        if (target) {
            target.innerHTML = html;
            this.attachEventHandlers(target, eventHandler);
        }
        
        if (response.styles) {
            this.injectStyles(response.styles);
        }
        
        if (response.meta && response.meta.title) {
            document.title = response.meta.title;
        }
        
        return true;
    }
    
    /**
     * Convert VDOM to HTML string (fallback)
     */
    vdomToHtml(node) {
        if (typeof node === 'string') {
            return this.escapeHtml(node);
        }
        
        // Resolve component reference if present
        if (node && node.component) {
            node = this.resolveComponent(node);
        }
        
        if (!node || !node.tag) {
            return '';
        }
        
        const attrs = [];
        if (node.props) {
            // Handle attrs
            if (node.props.attrs) {
                for (const [key, value] of Object.entries(node.props.attrs)) {
                    attrs.push(`${key}="${this.escapeHtml(String(value))}"`);
                }
            }
            // Handle style
            if (node.props.style) {
                const styleStr = Object.entries(node.props.style)
                    .map(([k, v]) => `${this.camelToKebab(k)}: ${v}`)
                    .join('; ');
                attrs.push(`style="${this.escapeHtml(styleStr)}"`);
            }
            // Handle class object
            if (node.props.class && typeof node.props.class === 'object') {
                const classes = Object.entries(node.props.class)
                    .filter(([_, v]) => v)
                    .map(([k]) => k)
                    .join(' ');
                if (classes) {
                    attrs.push(`class="${this.escapeHtml(classes)}"`);
                }
            }
        }
        
        const attrStr = attrs.length ? ' ' + attrs.join(' ') : '';
        const children = (node.children || []).map(c => this.vdomToHtml(c)).join('');
        
        // Self-closing tags
        const selfClosing = ['br', 'hr', 'img', 'input', 'meta', 'link'];
        if (selfClosing.includes(node.tag)) {
            return `<${node.tag}${attrStr} />`;
        }
        
        return `<${node.tag}${attrStr}>${children}</${node.tag}>`;
    }
    
    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
    
    camelToKebab(str) {
        return str.replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase();
    }
    
    /**
     * Attach event handlers to interactive elements (fallback)
     */
    attachEventHandlers(container, eventHandler) {
        const interactiveElements = container.querySelectorAll('[data-infinidom-interactive="true"]');
        interactiveElements.forEach(el => {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                eventHandler(e, 'click', el);
            });
        });
    }
    
    /**
     * Replace content at target
     */
    replaceContent(vnode, target) {
        let targetEl = this.container;
        
        // For body-level replacement, we need to handle page navigation properly
        // The issue: after streaming appends, currentVNode doesn't reflect actual DOM state
        // Solution: reset state and patch against actual body for clean navigation
        const isBodyReplace = !target || target === 'body';
        
        if (isBodyReplace) {
            // For body replacement (page navigation), we need a clean slate
            // Clear the existing content and reset vnode tracking
            const appContainer = document.getElementById('app') || document.body;
            
            // Reset the vnode tracking - we're starting fresh
            this.currentVNode = null;
            
            // Clear existing content to prevent stacking
            appContainer.innerHTML = '';
            
            // Patch against the now-empty container
            this.currentVNode = this.patch(appContainer, vnode);
            this.container = this.currentVNode.elm;
            return;
        }
        
        // For non-body targets, use querySelector
        targetEl = document.querySelector(target);
        
        if (!targetEl) {
            console.error(`Target element not found: ${target}`);
            return;
        }
        
        // If we have a current vnode for this target, patch it
        if (this.currentVNode && targetEl === this.container) {
            this.currentVNode = this.patch(this.currentVNode, vnode);
        } else {
            // First render - patch against the real element
            this.currentVNode = this.patch(targetEl, vnode);
            this.container = this.currentVNode.elm;
        }
    }
    
    /**
     * Append content to target
     */
    appendContent(vnode, target) {
        const targetEl = target ? document.querySelector(target) : this.container;
        if (!targetEl) return;
        
        const tempDiv = document.createElement('div');
        const tempVNode = this.patch(tempDiv, vnode);
        targetEl.appendChild(tempVNode.elm);
    }
    
    /**
     * Prepend content to target
     */
    prependContent(vnode, target) {
        const targetEl = target ? document.querySelector(target) : this.container;
        if (!targetEl) return;
        
        const tempDiv = document.createElement('div');
        const tempVNode = this.patch(tempDiv, vnode);
        targetEl.insertBefore(tempVNode.elm, targetEl.firstChild);
    }
    
    /**
     * Clear all children from target element
     */
    clearContent(target) {
        const targetEl = target ? document.querySelector(target) : this.container;
        if (!targetEl) return;
        
        // Remove all children
        targetEl.innerHTML = '';
    }
    
    /**
     * Remove an element from the DOM
     */
    removeElement(target) {
        const targetEl = document.querySelector(target);
        if (!targetEl) {
            console.warn(`Remove target not found: ${target}`);
            return;
        }
        targetEl.remove();
    }
    
    /**
     * Update/merge content at target
     */
    updateContent(vnode, target) {
        // For now, treat update as replace
        this.replaceContent(vnode, target);
    }
    
    /**
     * Inject CSS styles into the page
     */
    injectStyles(css) {
        let styleEl = document.getElementById('infinidom-injected-styles');
        
        if (!styleEl) {
            styleEl = document.createElement('style');
            styleEl.id = 'infinidom-injected-styles';
            document.head.appendChild(styleEl);
        }
        
        styleEl.textContent = css;
    }
    
    /**
     * Execute scripts (use with caution)
     */
    executeScripts(scripts) {
        try {
            // Create a function to execute in a somewhat sandboxed context
            const fn = new Function(scripts);
            fn();
        } catch (error) {
            console.error('Error executing scripts:', error);
        }
    }
    
    /**
     * Apply a single streaming operation
     * Used for progressive page building
     */
    applyOperation(operation, eventHandler) {
        if (!operation || !operation.type) {
            console.warn('Invalid operation:', operation);
            return false;
        }
        
        try {
            switch (operation.type) {
                case 'op':
                    return this.applyDOMOperation(operation, eventHandler);
                case 'style':
                    this.injectStyles(operation.css);
                    return true;
                case 'meta':
                    if (operation.title) {
                        document.title = operation.title;
                    }
                    // Return path for URL update handling
                    return { path: operation.path };
                default:
                    console.warn('Unknown operation type:', operation.type);
                    return false;
            }
        } catch (error) {
            console.error('Error applying operation:', error, operation);
            return false;
        }
    }
    
    /**
     * Apply a DOM operation (replace, append, prepend)
     */
    applyDOMOperation(operation, eventHandler) {
        const { op, target, element } = operation;
        
        // Clear operation doesn't need an element
        if (op === 'clear') {
            if (this.useFallback) {
                return this.applyDOMOperationFallback(operation, eventHandler);
            }
            this.clearContent(target);
            return true;
        }
        
        // Remove operation doesn't need an element
        if (op === 'remove') {
            if (this.useFallback) {
                return this.applyDOMOperationFallback(operation, eventHandler);
            }
            this.removeElement(target);
            return true;
        }
        
        if (!element) {
            console.warn('Operation missing element:', operation);
            return false;
        }
        
        // If using fallback (no Snabbdom), use fallback rendering
        if (this.useFallback) {
            return this.applyDOMOperationFallback(operation, eventHandler);
        }
        
        // Convert element to VNode
        const vnode = this.toVNode(element, eventHandler);
        
        switch (op) {
            case 'replace':
                this.replaceContent(vnode, target);
                break;
            case 'append':
                this.appendContent(vnode, target);
                break;
            case 'prepend':
                this.prependContent(vnode, target);
                break;
            default:
                console.warn('Unknown DOM operation:', op);
                return false;
        }
        
        return true;
    }
    
    /**
     * Fallback for DOM operations without Snabbdom
     */
    applyDOMOperationFallback(operation, eventHandler) {
        const { op, target, element } = operation;
        
        let targetEl;
        if (target === 'body') {
            targetEl = document.body;
        } else if (target) {
            targetEl = document.querySelector(target);
        }
        
        if (!targetEl) {
            // Try to find app container
            targetEl = document.getElementById('app') || document.body;
        }
        
        // Handle clear operation (doesn't need element)
        if (op === 'clear') {
            targetEl.innerHTML = '';
            return true;
        }
        
        // Handle remove operation (doesn't need element)
        if (op === 'remove') {
            const removeEl = document.querySelector(target);
            if (removeEl) removeEl.remove();
            return true;
        }
        
        const html = this.vdomToHtml(element);
        
        switch (op) {
            case 'replace':
                targetEl.innerHTML = html;
                break;
            case 'append':
                targetEl.insertAdjacentHTML('beforeend', html);
                break;
            case 'prepend':
                targetEl.insertAdjacentHTML('afterbegin', html);
                break;
        }
        
        // Attach event handlers
        this.attachEventHandlers(targetEl, eventHandler);
        return true;
    }
    
    /**
     * Show loading overlay
     */
    showLoading() {
        let overlay = document.querySelector('.infinidom-loading-overlay');
        
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'infinidom-loading-overlay';
            overlay.innerHTML = '<div class="infinidom-loading-spinner"></div>';
            document.body.appendChild(overlay);
        }
        
        // Trigger reflow for animation
        overlay.offsetHeight;
        overlay.classList.add('active');
    }
    
    /**
     * Hide loading overlay
     */
    hideLoading() {
        const overlay = document.querySelector('.infinidom-loading-overlay');
        if (overlay) {
            overlay.classList.remove('active');
        }
    }
}

// Export for use in other modules
window.InfinidomDOMPatcher = InfinidomDOMPatcher;
