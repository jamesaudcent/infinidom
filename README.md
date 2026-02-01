# infinidom

AI-powered dynamic website generator. Provide your content, and AI builds an infinite, explorable website in real-time.

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
    └── prompt.txt           # AI personality
```

### 1. Create your site folder

```bash
mkdir -p sites/mysite/content
```

### 2. Add your content

Put any files in `sites/mysite/content/`. Text files (.md, .txt, .json, .yaml) are read and provided to the AI. Images can be placed directly or in subfolders.

```markdown
# My Company

We build amazing products...

## Services
- Service A
- Service B

## Contact
email@example.com
```

### 3. Customize the AI personality

Edit `sites/mysite/prompt.txt`:

```
You are the voice of My Company.
Be professional but friendly.
Always highlight our commitment to quality.
Navigation: Home, About, Services, Contact
```

### 4. Register your site

Add to `sites/config.yaml`:

```yaml
sites:
  mysite:
    domains:
      - mysite.com
      - localhost  # for local testing
    name: "My Company"
    theme: dark
```

### 5. Restart and visit

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
| `AI_MAX_TOKENS` | `16384` | Max tokens for responses |
| `CONTENT_MODE` | `expansive` | `expansive` or `restrictive` |
| `PERSIST_SESSION` | `true` | Resume previous session on return (set `false` for testing) |
| `PORT` | `8000` | Server port |

### Site Configuration

In `sites/config.yaml`:

```yaml
defaults:
  theme: light

sites:
  mysite:
    domains:
      - mysite.com
      - www.mysite.com
    name: "My Site Name"
    theme: dark  # override default
```

### Content Modes

- **expansive**: AI uses your content as inspiration, creating rich explorable pages
- **restrictive**: AI strictly adheres to your provided content only

### Page Caching

infinidom includes intelligent caching at multiple levels (always enabled within a session):

- **Backend cache**: Pages are cached server-side per session. Revisiting a page returns cached content instantly
- **Frontend cache**: Pages are cached in-browser for instant back/forward navigation
- **Conversation persistence**: The AI maintains context across all interactions, so it understands the user's journey even when serving cached pages

Navigation buttons use `data-path` attributes to enable instant cache lookups:
```json
{"tag":"button","props":{"attrs":{"data-infinidom-interactive":"true","data-path":"/features"}},"children":["Features"]}
```

Set `PERSIST_SESSION=false` to start fresh on each visit (useful for testing). When true, returning users resume their previous session with all cached pages intact.

---

## Development

For local development with source code:

### Clone the repository

```bash
git clone https://github.com/jamesaudcent/infinidom.git
cd infinidom
```

### Run with local builds

```bash
docker compose -f docker-compose.dev.yaml up --build
```

### Running without Docker

Prerequisites: Python 3.11+

```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
python run.py
```

---

## Multi-Site Hosting

Run multiple sites from a single instance:

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

Each site has its own content folder and the framework routes requests based on the domain.

---

## License

MIT
