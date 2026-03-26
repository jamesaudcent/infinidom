# infinidom

AI-powered dynamic website generator. Provide your content and a personality prompt; the AI builds an infinite, explorable website in real-time by streaming DOM operations to the browser.

## How It Works

infinidom does not serve static HTML pages. Instead, a FastAPI backend sends your site content and a system prompt to an LLM (OpenAI or Cerebras), which responds with a stream of atomic JSON DOM operations. The browser applies these operations in real-time using [Snabbdom](https://github.com/snabbdom/snabbdom) (virtual DOM) with a native DOM fallback.

```
Browser ──GET /api/stream/init──▶ FastAPI ──chat completion──▶ LLM
   ◀──SSE: JSON ops (append, clear, meta, style, finish)──┘
```

Each interaction (click, form submit, navigation) streams a new set of operations via `POST /api/stream/interact`. Pages are cached at both the server (per session) and client (in-browser `Map`) layers, so revisiting a page is instant. The AI maintains full conversation context across interactions, understanding the user's journey even when serving from cache.

## Architecture

```
├── backend/                    # Python / FastAPI
│   ├── main.py                 # App setup, CORS, SiteMiddleware, static mount
│   ├── config.py               # Pydantic Settings (env-backed)
│   ├── middleware/sites.py     # Host header → site resolution
│   ├── routes/api.py           # All HTTP/SSE endpoints
│   ├── services/
│   │   ├── ai_service.py       # LLM streaming, JSON op parsing, page caching
│   │   ├── content_service.py  # Reads site content files (.md, .txt, .json, .yaml)
│   │   ├── site_loader.py      # Loads sites/config.yaml, maps domains to sites
│   │   └── system_prompt.py    # Streaming system prompt (atomic JSON op format)
│   ├── models/                 # Pydantic request/response schemas
│   └── utils/session_manager.py # In-memory session store with TTL
├── frontend/                   # Vanilla JS (no React/Vue)
│   ├── index.html              # Shell: Tailwind CDN, Snabbdom import map, loaders
│   ├── css/styles.css          # Transitions, loading states, interactive cursors
│   └── js/
│       ├── api-client.js       # SSE streaming, fetch interactions, client page cache
│       ├── dom-patcher.js      # Snabbdom patching, op/meta/style/finish handling
│       └── random.js           # Main Infinidom class: init, event delegation, caching
├── sites/                      # User-provided content (gitignored, runtime data)
│   ├── config.yaml             # Domain → site mapping + theme defaults
│   └── <site-id>/
│       ├── content/            # .md, .txt, .json, .yaml, images
│       ├── prompt.txt          # AI personality for this site
│       └── styles.css          # Optional site-specific styles
├── run.py                      # Uvicorn entry point
├── Dockerfile                  # Production image (Python 3.11-slim)
├── docker-compose.yaml         # Published image + sites volume mount
├── docker-compose.dev.yaml     # Local build variant
├── fly.toml                    # Fly.io deployment (region: syd, volume for sites)
└── .github/workflows/fly-deploy.yml  # CI: deploy to Fly.io on push to main
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| AI | OpenAI SDK, Cerebras Cloud SDK (configurable) |
| Frontend | Vanilla JS, Snabbdom (virtual DOM via esm.sh CDN), Tailwind CSS (CDN) |
| Validation | Pydantic v2, pydantic-settings |
| Deployment | Docker, Fly.io (with persistent volume for sites) |
| Sessions | In-memory with TTL (no database) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serves the frontend HTML shell |
| `GET` | `/api/stream/init` | SSE stream: initial page load (cached or AI-generated) |
| `POST` | `/api/stream/interact` | SSE stream: handles user interactions (clicks, forms, nav) |
| `POST` | `/api/notify/navigation` | Syncs AI context when client serves a cached page |
| `GET` | `/api/config` | Returns site name, theme, content mode, framework info |
| `GET` | `/api/health` | Health check with active session count |
| `GET` | `/site-styles.css` | Site-specific CSS or default styles |
| `GET` | `/{path}` | SPA catchall; serves images from site `content/` by filename |

## Quick Start

### 1. Create your project folder

```bash
mkdir my-site && cd my-site
```

### 2. Download the compose file

```bash
curl -O https://raw.githubusercontent.com/jamesaudcent/infinidom/main/docker-compose.yaml
```

### 3. Create your sites folder

```bash
mkdir -p sites/mysite/content
```

Add a `sites/config.yaml`:
```yaml
sites:
  mysite:
    domains:
      - localhost
    name: "My Site"
```

Add content in `sites/mysite/content/` and a `sites/mysite/prompt.txt` for AI personality.

### 4. Set your API key

```bash
export AI_API_KEY=sk-your-key-here
```

Or create a `.env` file:
```
AI_API_KEY=sk-your-key-here
```

### 5. Run with Docker

```bash
docker compose up
```

Your site is now live at **http://localhost:8000**

---

## Creating Your Site

### Folder Structure

```
sites/
├── config.yaml              # Site configuration
└── mysite/
    ├── content/             # Your content (text, images, anything)
    │   ├── about.md
    │   ├── services.txt
    │   ├── images/          # Images can be in subfolders
    │   │   └── logo.png
    │   └── products.json
    ├── prompt.txt           # AI personality
    └── styles.css           # Optional site-specific styles
```

### 1. Add your content

Put any files in `sites/mysite/content/`. Text files (.md, .txt, .json, .yaml) are read and provided to the AI. Images can be placed directly or in subfolders and are served by filename.

```markdown
# My Company

We build amazing products...

## Services
- Service A
- Service B

## Contact
email@example.com
```

### 2. Customize the AI personality

Edit `sites/mysite/prompt.txt`:

```
You are the voice of My Company.
Be professional but friendly.
Always highlight our commitment to quality.
Navigation: Home, About, Services, Contact
```

### 3. Register your site

Add to `sites/config.yaml`:

```yaml
defaults:
  theme: light

sites:
  mysite:
    domains:
      - mysite.com
      - localhost
    name: "My Company"
    theme: dark  # override default
```

### 4. Restart and visit

```bash
docker compose restart
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_API_KEY` | - | Your API key (required) |
| `AI_PROVIDER` | `openai` | AI provider: `openai` or `cerebras` |
| `AI_MODEL` | `gpt-4o-mini` | Model to use |
| `AI_MAX_TOKENS` | `16384` | Max tokens per response |
| `CONTENT_MODE` | `expansive` | `expansive` or `restrictive` |
| `PERSIST_SESSION` | `true` | Resume previous session on return |
| `SESSION_TTL_SECONDS` | `3600` | Session expiry in seconds |
| `MAX_SESSION_HISTORY` | `20` | Max interactions kept in session |
| `PORT` | `8000` | Server port |
| `HOST` | `0.0.0.0` | Server host |
| `DEBUG` | `false` | Enable debug mode / hot reload |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

### Content Modes

- **expansive**: AI uses your content as inspiration, creating rich explorable pages
- **restrictive**: AI strictly adheres to your provided content only

### Page Caching

infinidom includes two-layer caching (always active within a session):

- **Server cache**: Pages are cached per session on the backend. Revisiting a page returns cached DOM ops instantly without calling the LLM.
- **Client cache**: Pages are cached in-browser via a `Map` for instant back/forward navigation and popstate handling.
- **Conversation context**: The AI maintains full context across interactions. When a cached page is served, the backend is notified via `/api/notify/navigation` so the conversation stays coherent.

Navigation buttons use `data-path` attributes for cache lookups:
```json
{"tag":"button","props":{"attrs":{"data-infinidom-interactive":"true","data-path":"/features"}},"children":["Features"]}
```

Set `PERSIST_SESSION=false` to start fresh on each visit (useful for testing). When true, returning users resume their previous session with all cached pages intact.

---

## Multi-Site Hosting

Run multiple sites from a single instance. Requests are routed by the `Host` header:

```yaml
# sites/config.yaml
sites:
  site-a:
    domains: [site-a.com]
    name: "Site A"

  site-b:
    domains: [site-b.com]
    name: "Site B"

  site-c:
    domains: [site-c.com]
    name: "Site C"
```

Each site has its own content folder, prompt, and optional styles. The middleware resolves the domain and makes the site context available to all routes.

---

## Development

### Clone and run locally

```bash
git clone https://github.com/jamesaudcent/infinidom.git
cd infinidom
```

### Docker (local build)

```bash
docker compose -f docker-compose.dev.yaml up --build
```

### Without Docker

Prerequisites: Python 3.11+

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python run.py
```

---

## Implemented Features

### AI Streaming DOM Generation

The core of infinidom. Rather than serving pre-built HTML, the backend sends site content and a system prompt to an LLM, which responds with a stream of atomic JSON DOM operations. `AIService.stream_dom_operations` opens an async streaming chat completion (OpenAI or Cerebras), then incrementally parses complete JSON objects from the token stream using a character-level brace-depth parser (`_extract_json_object`). Each parsed object is yielded immediately to the SSE response, so the browser renders elements as they arrive. The LLM signals completion with a `{"type":"finish"}` object. Supported operations:

- `clear` -- remove all children from a target container
- `remove` -- remove a specific element by selector
- `append` -- add an element to a target (the primary building operation)
- `meta` -- set page title and path (triggers `history.pushState` on the client)
- `style` -- inject CSS into the page
- `finish` -- signal that the page is complete

The system prompt (`system_prompt.py`) instructs the LLM to emit one element per operation using Tailwind CSS classes, assign IDs to containers for targeting, mark interactive elements with `data-infinidom-interactive="true"`, and include `data-path` attributes on navigation buttons for caching.

### Snabbdom Virtual DOM Patching

The frontend uses [Snabbdom](https://github.com/snabbdom/snabbdom) loaded via an ESM import map from esm.sh. `InfinidomDOMPatcher` initializes Snabbdom with class, props, style, attributes, and event listener modules. When a streaming `op` arrives, `applyOperation` dispatches to `applyDOMOperation`, which converts the JSON element to a Snabbdom VNode via `toVNode` and calls `appendContent`, `replaceContent`, `clearContent`, or `removeElement` as appropriate. `appendContent` patches a temporary div to materialize the VNode, then appends the resulting real DOM element to the target. If Snabbdom fails to load within 5 seconds, the patcher falls back to `innerHTML`-based rendering with `vdomToHtml` and manual event handler attachment.

### SSE-Based Communication

Two distinct streaming paths connect frontend and backend:

- **Initial page load** (`GET /api/stream/init`): Uses the browser-native `EventSource` API. The client passes `session_id` and `path` as query parameters. The server responds with SSE events: a `session` event (carrying the session ID), then either `cached` + replayed operations or live-streamed LLM operations, followed by a `complete` event. `InfinidomAPIClient._streamRequest` manages the EventSource lifecycle.

- **Interactions** (`POST /api/stream/interact`): Since `EventSource` only supports GET, interactions use `fetch` with a `ReadableStream` reader. The client sends a JSON body containing the event data, session ID, current URL, viewport dimensions, and the current `document.body.innerHTML`. `InfinidomAPIClient.streamInteract` reads chunks from the response, splits on newlines, and parses `data:` prefixed SSE lines. Both paths use the same JSON operation format.

### Persistent AI Conversation

The AI maintains a single conversation thread per session stored in `SessionContext.ai_messages`. On the first request, `_build_messages` constructs a full context: the system prompt (with content mode instructions appended), site info, site-specific prompt, all site content, and the triggering event. This is stored in the session. On subsequent requests, only a minimal event message is appended via `build_event_message` (e.g., `User clicked: "About" (button)`), and the full existing message history is sent to the LLM. After each response, `_store_response` appends both the user message and assistant response to `session.ai_messages`. This gives the AI complete awareness of every page it has generated and every interaction the user has taken.

### Two-Layer Page Caching

Pages are cached independently at two levels, both always active within a session:

- **Server cache**: When `AIService.stream_dom_operations` completes, it calls `session.cache_page(path, operations_list)`, storing the list of JSON operations in `SessionContext.page_cache` keyed by path. On the next request for the same path, `stream_initial_load` checks `session.get_cached_page(path)` first and streams the cached operations directly without calling the LLM.

- **Client cache**: `InfinidomAPIClient` maintains a `Map` of `path -> {operations, timestamp}`. After a page streams in (initial load or interaction), the operations array is stored via `cachePage`. Before any server request, `streamInit` and `handleEventStreaming` check `hasPageCached(path)`. Cached pages are replayed by iterating the stored operations through `domPatcher.applyOperation`.

When the client serves a page from its local cache, it fires `notifyNavigation(path)` which POSTs to `/api/notify/navigation`. The backend calls `AIService.add_navigation_context`, which inserts a synthetic message like `[System: User navigated back to /about (served from cache)]` into the conversation thread so the LLM stays aware of the user's location.

### Session Management

`SessionManager` stores `SessionContext` objects in an in-memory dictionary protected by a threading `Lock`. Each session has a UUID, creation/last-accessed timestamps, an interaction history list, the `ai_messages` conversation thread, and the `page_cache` dictionary. Sessions expire after `SESSION_TTL_SECONDS` (default 3600). Expired sessions are cleaned up lazily during `get_or_create_session` and `get_session_count` calls.

On the client side, `InfinidomAPIClient` persists the session ID in `localStorage` under the key `infinidom_session_id`. On page load, the stored ID is sent as a query parameter to `/api/stream/init`. If `PERSIST_SESSION` is true, the server looks up the existing session and resumes it (cached pages and conversation intact). If false, the server ignores the ID and creates a fresh session every time.

### Multi-Site Hosting

A single infinidom instance can serve multiple sites. `SiteLoader` reads `sites/config.yaml` at startup, building a `Site` dataclass for each entry (with `id`, `path`, `name`, `domains` list, and `theme`) and a reverse map from domain to site ID. `SiteMiddleware` runs on every request: it reads the `Host` header, strips the port, calls `get_site_by_domain`, and attaches the result to `request.state.site`. Route handlers call `get_site_or_404(request)` to retrieve the resolved site or return a 404 if the domain isn't mapped. Each site gets its own `AIService` instance (cached by site ID), its own `ContentService`, its own content folder, prompt file, and optional stylesheet.

### Per-Site Content Loading

`ContentService` recursively reads all text files (`.md`, `.txt`, `.json`, `.yaml`, `.yml`) from a site's `content/` directory using `aiofiles`. Each file is cached in memory after first read. `get_all_content` concatenates them with `---` separators, prefixed by relative path headers (e.g., `### about.md`). `get_site_prompt` reads `prompt.txt` from the site root. This content is included in the initial system message sent to the LLM, giving it the raw material to build pages from. Currently `get_relevant_content` returns everything; it's designed as an extension point for future semantic or keyword-based content selection.

### Content Modes

Two modes control how the AI uses site content, set via the `CONTENT_MODE` environment variable:

- **Expansive** (default): Appends the instruction "Use the provided content as inspiration. Generate rich, explorable content with interactive elements." The AI treats your content as a starting point and creates a full, navigable website experience.

- **Restrictive**: Appends "Only use information from the provided content. Do not invent content." The AI stays strictly within the bounds of what you've provided.

The instruction is appended to the system prompt in `_build_messages` via `get_content_mode_instructions()`.

### Event Delegation and Interaction Capture

The `Infinidom` class in `random.js` sets up document-level event delegation for clicks, form submissions, and input changes. Click handling intercepts elements marked with `data-infinidom-interactive="true"` as well as any `<a>` or `<button>` element. External links (different origin, `target="_blank"`, `mailto:`, `tel:`) are allowed through to the browser. For captured clicks, `buildEventData` constructs a payload including: event type, target tag/text/ID/classes, href, `data-path`, input value, all `data-*` attributes, a CSS selector, form data (for submit events), and a DOM element hierarchy. `buildElementHierarchy` walks up from the clicked element to the body (max 10 levels), extracting tag names, IDs, semantic classes (filtering out Tailwind utility classes via regex), data attributes, ARIA labels, and contextual text (heading content, section labels, etc.). This hierarchy gives the AI context about what a generic "Learn More" button relates to.

### Browser History and Navigation

When a `meta` operation arrives with a `path` field, the frontend calls `history.pushState` to update the URL without a page reload. The `popstate` event listener handles browser back/forward: it checks the client page cache first, and if the page is cached, replays the operations instantly and notifies the backend. If not cached, it falls back to `loadInitialContent` which streams from the server. Navigation buttons with `data-path` attributes enable the same cache-first behavior for forward navigation within the site.

### Per-Site Styling

Each site can provide a `styles.css` file alongside its `prompt.txt`. The `/site-styles.css` endpoint checks for the site's custom stylesheet first, falls back to the default `frontend/css/styles.css`, or returns an empty CSS comment. The frontend HTML shell loads this endpoint via a `<link>` tag on every page. The default stylesheet provides cursor styling for interactive elements (`[data-infinidom-interactive]`), CSS transitions for content appearance, and loading overlay/spinner styles.

### Image Serving

Images placed in a site's `content/` directory (or any subdirectory) are served via the catchall route `GET /{path}`. When the requested path has an image extension (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`, `.ico`), the handler first tries the exact path under `site.content_path`, then falls back to a recursive filename search using `rglob`. This means the AI can reference images by just their filename (e.g., `src="logo.png"`) regardless of subfolder structure, which is what the system prompt instructs it to do.

### Configurable AI Provider

`AIService.__init__` reads `AI_PROVIDER` from settings. If set to `cerebras`, it instantiates `AsyncCerebras` from the Cerebras Cloud SDK (with a helpful import error if the package is missing). Otherwise it defaults to `AsyncOpenAI`. The streaming request differs slightly between providers: Cerebras uses `max_completion_tokens` with temperature 1, while OpenAI uses `max_tokens` with temperature 0.7. Both use the same streaming response parsing. The Fly.io deployment defaults to Cerebras with the `gpt-oss-120b` model.

### Health Check and Client Config

`GET /api/health` returns the framework name, status, and active session count (cleaned of expired sessions). It's the only endpoint that doesn't require a resolved site, making it suitable for load balancer health probes. `GET /api/config` returns the content mode, site name, site theme, and framework identifier, giving the frontend access to server-side configuration.

### Docker and Fly.io Deployment

The `Dockerfile` builds a Python 3.11-slim image, installs dependencies from `requirements.txt`, copies `backend/`, `frontend/`, and `run.py`, declares a volume at `/app/sites`, and runs `python run.py`. `docker-compose.yaml` uses the published image `jamesaudcent/infinidom:latest` with a `./sites` bind mount and environment variables for the AI provider. `docker-compose.dev.yaml` builds from source instead. `fly.toml` configures a Fly.io app in the `syd` region with a persistent volume (`sites_data` mounted at `/app/sites`), auto-stop/start machines, a 1GB VM, and env defaults for Cerebras.

### CI/CD

`.github/workflows/fly-deploy.yml` triggers on push to `main`. It runs `flyctl deploy --remote-only` using a `FLY_API_TOKEN` secret. There are no test or lint steps in the pipeline.

### Performance Instrumentation

The `Infinidom` class includes built-in performance timing. `startTiming` / `endTiming` measure wall-clock durations using `performance.now()`. Every streaming interaction logs time-to-first-operation and total time with operation count. `getPerformanceSummary()` aggregates all collected timings by label, computing count, average, min, and max, and displays them via `console.table`.

### Known Gaps

- **No automated tests** -- no pytest, unittest, or test files exist in the project
- **`PyYAML` missing from `requirements.txt`** -- `site_loader.py` imports `yaml` but the dependency is not listed; clean installs may fail
- **`/api/ui/components` endpoint not implemented** -- the frontend `dom-patcher.js` attempts to fetch a component library from this route, but no backend handler exists; the component resolution path is effectively dead code
- **`DOMResponse` / `VirtualDOMNode` models unused** -- `backend/models/response.py` defines structured response types, but the streaming path uses ad-hoc JSON ops directly; these models are legacy/aspirational
- **`SessionManager.add_interaction` / `update_session_dom` never called** -- defined utility methods that are not wired into any route or service
- **`InitialLoadRequest` model unused** -- the init endpoint uses query params instead
- **Content selection is a stub** -- `ContentService.get_relevant_content` returns all content; smarter semantic/keyword filtering is noted as a future enhancement
- **Sessions are in-memory only** -- comments note Redis (or similar) should replace the in-memory store for production resilience
- **No authentication or authorization** -- endpoints are open; session identity is an opaque UUID in `localStorage`
- **Legacy naming** -- `package.json` and `requirements.txt` still reference "RanDOM" / `random-framework`

---

## License

MIT
