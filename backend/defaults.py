"""Default file contents for new infinidom sites."""
from pathlib import Path

from backend.services.site_loader import Site

DEFAULT_PROMPT = """\
You are the AI behind this website.
Be helpful, friendly, and professional.
Create engaging, well-structured pages with clear navigation.
Use interactive elements to encourage exploration.

Design notes:
- Maintain a consistent navigation bar across pages
- Adhere to web design best practice
- Provide buttons and links for users to go deeper at each stage
- Navigation buttons should include data-path attributes for instant cached navigation
- For external links use regular anchor tags with target="_blank"
"""

DEFAULT_CONTENT = """\
# infinidom

**AI-powered dynamic website generator.**

infinidom is a web framework where AI dynamically generates web pages in real-time. \
Provide your content and a personality prompt, and AI builds an infinite, explorable \
website — streaming DOM operations directly to the browser as users navigate.

No templates. No static HTML. Every page is generated on-demand.

---

## How It Works

1. **User visits a URL** — the request goes to the infinidom server
2. **AI receives context** — site content, session history, current path
3. **AI generates DOM operations** — JSON instructions streamed to the browser
4. **Browser renders progressively** — elements appear as they are generated

The AI maintains full conversation context across interactions, so it understands the \
user's journey even when serving cached pages.

---

## Key Features

### Real-Time Generation
Every page is generated fresh by the AI based on your content, the URL, and user context.

### Multi-Site Hosting
Run multiple sites from a single instance. Each site gets its own content, prompt, \
domain routing, and theme.

### Intelligent Caching
Pages are cached at both the server and client level. Revisiting a page is instant. \
The AI conversation stays in sync even when serving from cache.

### Content Modes
- **Expansive** (default): AI uses your content as inspiration and creates rich pages
- **Restrictive**: AI strictly adheres to the content you provide

### AI Provider Flexibility
Works with OpenAI (GPT-4o-mini, GPT-4o, etc.) or Cerebras for ultra-fast inference.

---

## Getting Started

Create a `sites/` folder with your content, add a `config.yaml` to map your domain, \
set your API key, and run with Docker:

```bash
docker compose up
```

Your AI-generated site is live at **http://localhost:8000**.

---

## Open Source

infinidom is open source under the MIT license.

**GitHub**: https://github.com/jamesaudcent/infinidom

---

*infinidom — where every page is a new beginning.*
"""

DEFAULT_STYLES = """\
/* Site Styles */

[data-infinidom-interactive="true"] {
    cursor: pointer;
}

.infinidom-transition {
    transition: opacity 0.3s ease, transform 0.3s ease;
}

.infinidom-fade-in {
    animation: infinidom-fade-in 0.5s ease forwards;
}

@keyframes infinidom-fade-in {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}

.infinidom-loading-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s ease;
}

.infinidom-loading-overlay.active {
    opacity: 1;
    pointer-events: all;
}

.infinidom-loading-spinner {
    width: 50px;
    height: 50px;
    border: 3px solid rgba(255, 255, 255, 0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}
"""

INFINIDOM_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="512" height="512">
  <path fill="#6366f1" d="M5.68 5.792 7.345 7.75 5.681 9.708a2.75 2.75 0 1 1 0-3.916ZM8 6.978 6.416 5.113l-.014-.015a3.75 3.75 0 1 0 0 5.304l.014-.015L8 8.522l1.584 1.865.014.015a3.75 3.75 0 1 0 0-5.304l-.014.015zm.656.772 1.663-1.958a2.75 2.75 0 1 1 0 3.916z"/>
</svg>
"""


def _parse_captions(text: str) -> dict[str, str]:
    """Parse captions.md into {filename: caption}."""
    captions: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            name, caption = line.split(":", 1)
            captions[name.strip()] = caption.strip()
    return captions


def _serialize_captions(captions: dict[str, str]) -> str:
    """Serialize {filename: caption} back to captions.md format."""
    lines = ["# Image Captions"]
    for name, caption in sorted(captions.items()):
        lines.append(f"{name}: {caption}")
    return "\n".join(lines) + "\n"


def ensure_site_defaults(site: Site):
    """Create missing default files for a site."""
    site.content_path.mkdir(parents=True, exist_ok=True)

    images_dir = site.content_path / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    if not site.prompt_path.exists() or site.prompt_path.stat().st_size <= 1:
        site.prompt_path.write_text(DEFAULT_PROMPT, encoding="utf-8")

    if not site.styles_path.exists() or site.styles_path.stat().st_size <= 1:
        site.styles_path.write_text(DEFAULT_STYLES, encoding="utf-8")

    content_md = site.content_path / "content.md"
    if not content_md.exists() or content_md.stat().st_size <= 1:
        content_md.write_text(DEFAULT_CONTENT, encoding="utf-8")

    logo_path = images_dir / "infinidom-logo.svg"
    if not logo_path.exists():
        logo_path.write_text(INFINIDOM_LOGO_SVG, encoding="utf-8")

    captions_path = images_dir / "captions.md"
    if not captions_path.exists() or captions_path.stat().st_size <= 1:
        captions_path.write_text("# Image Captions\ninfinidom-logo.svg: The infinidom infinity logo\n", encoding="utf-8")
