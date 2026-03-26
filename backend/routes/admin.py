"""Admin routes for managing sites, content, and runtime settings."""
import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from backend.config import get_settings, update_settings
from backend.defaults import _parse_captions, _serialize_captions, ensure_site_defaults
from backend.services.ai_service import reset_ai_services
from backend.services.site_loader import Site, get_site_loader


admin_router = APIRouter(prefix="/admin")
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".css", ".html", ".js"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"}

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SiteCreateRequest(BaseModel):
    id: str
    name: Optional[str] = None

class SiteUpdateRequest(BaseModel):
    name: Optional[str] = None
    theme: Optional[str] = None
    domains: Optional[list[str]] = None
    content_mode: Optional[str] = None
    contact_email: Optional[str] = None

class ContentUpdateRequest(BaseModel):
    content: str

class PromptUpdateRequest(BaseModel):
    content: str

class StylesUpdateRequest(BaseModel):
    content: str

class ImageCaptionUpdate(BaseModel):
    caption: str

class SettingsUpdateRequest(BaseModel):
    ai_provider: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None
    ai_max_tokens: Optional[int] = None
    content_mode: Optional[str] = None
    persist_session: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_site(site_id: str) -> Site:
    site = get_site_loader().get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return site


def _resolve_content_path(base_path: Path, relative_path: str) -> Path:
    candidate = (base_path / relative_path).resolve()
    base_resolved = base_path.resolve()
    if not str(candidate).startswith(str(base_resolved)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    return candidate


def _images_dir(site: Site) -> Path:
    d = site.content_path / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Admin HTML pages
# ---------------------------------------------------------------------------

@admin_router.get("")
@admin_router.get("/")
async def admin_root():
    return RedirectResponse(url="/admin/sites", status_code=302)


@admin_router.get("/sites")
async def serve_sites_dashboard():
    path = FRONTEND_DIR / "admin-sites.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Admin dashboard not found")
    return FileResponse(str(path), media_type="text/html")


@admin_router.get("/sites/{site_id}")
async def serve_site_admin(site_id: str):
    _get_site(site_id)
    path = FRONTEND_DIR / "admin.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Admin UI not found")
    return FileResponse(str(path), media_type="text/html")


# ---------------------------------------------------------------------------
# Global sites API
# ---------------------------------------------------------------------------

@admin_router.get("/api/sites")
async def list_all_sites():
    loader = get_site_loader()
    return {
        "sites": [
            {
                "id": s.id,
                "name": s.name,
                "theme": s.theme,
                "domains": s.domains,
                "contact_email": s.contact_email,
            }
            for s in loader.list_sites()
        ]
    }


@admin_router.post("/api/sites")
async def create_site(body: SiteCreateRequest):
    loader = get_site_loader()
    site_id = body.id.strip().lower().replace(" ", "-")
    if not site_id:
        raise HTTPException(status_code=400, detail="Site ID is required")
    if loader.get_site(site_id):
        raise HTTPException(status_code=409, detail=f"Site '{site_id}' already exists")
    site = loader.create_site(site_id, name=body.name or site_id)
    ensure_site_defaults(site)
    return {
        "id": site.id,
        "name": site.name,
        "theme": site.theme,
        "domains": site.domains,
        "contact_email": site.contact_email,
    }


@admin_router.delete("/api/sites/{site_id}")
async def delete_site(site_id: str):
    loader = get_site_loader()
    if not loader.get_site(site_id):
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    loader.delete_site(site_id, remove_files=True)
    return {"status": "ok", "id": site_id}


# ---------------------------------------------------------------------------
# Per-site: config
# ---------------------------------------------------------------------------

@admin_router.get("/api/sites/{site_id}/site")
async def get_site_info(site_id: str):
    site = _get_site(site_id)
    return {
        "id": site.id,
        "name": site.name,
        "theme": site.theme,
        "domains": site.domains,
        "content_mode": site.content_mode,
        "contact_email": site.contact_email,
    }


@admin_router.put("/api/sites/{site_id}/site")
async def update_site_info(site_id: str, body: SiteUpdateRequest):
    _get_site(site_id)
    if (
        body.name is None
        and body.theme is None
        and body.domains is None
        and body.content_mode is None
        and body.contact_email is None
    ):
        raise HTTPException(status_code=400, detail="No fields provided")
    loader = get_site_loader()
    updated = loader.update_site_config(
        site_id,
        name=body.name,
        theme=body.theme,
        domains=body.domains,
        content_mode=body.content_mode,
        contact_email=body.contact_email,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Site config not found")
    return {
        "id": updated.id,
        "name": updated.name,
        "theme": updated.theme,
        "domains": updated.domains,
        "content_mode": updated.content_mode,
        "contact_email": updated.contact_email,
    }


# ---------------------------------------------------------------------------
# Per-site: content files (excludes images/ subfolder)
# ---------------------------------------------------------------------------

@admin_router.get("/api/sites/{site_id}/content")
async def list_content_files(site_id: str):
    site = _get_site(site_id)
    images_dir = (site.content_path / "images").resolve()
    files = []
    if site.content_path.exists():
        for file_path in sorted(site.content_path.rglob("*")):
            if not file_path.is_file() or file_path.name.startswith("."):
                continue
            if str(file_path.resolve()).startswith(str(images_dir)):
                continue
            rel = str(file_path.relative_to(site.content_path))
            suffix = file_path.suffix.lower()
            files.append({
                "path": rel,
                "name": file_path.name,
                "size": file_path.stat().st_size,
                "is_text": suffix in TEXT_EXTENSIONS,
                "extension": suffix,
            })
    return {"files": files}


@admin_router.get("/api/sites/{site_id}/content/{filepath:path}")
async def read_content_file(site_id: str, filepath: str):
    site = _get_site(site_id)
    full_path = _resolve_content_path(site.content_path, filepath)
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    suffix = full_path.suffix.lower()
    if suffix not in TEXT_EXTENSIONS:
        return {"path": filepath, "is_text": False, "content": None}
    return {"path": filepath, "is_text": True, "content": full_path.read_text(encoding="utf-8")}


@admin_router.put("/api/sites/{site_id}/content/{filepath:path}")
async def write_content_file(site_id: str, filepath: str, body: ContentUpdateRequest):
    site = _get_site(site_id)
    full_path = _resolve_content_path(site.content_path, filepath)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(body.content, encoding="utf-8")
    return {"status": "ok", "path": filepath}


@admin_router.delete("/api/sites/{site_id}/content/{filepath:path}")
async def delete_content_file(site_id: str, filepath: str):
    site = _get_site(site_id)
    full_path = _resolve_content_path(site.content_path, filepath)
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    full_path.unlink()
    return {"status": "ok", "path": filepath}


# ---------------------------------------------------------------------------
# Per-site: images
# ---------------------------------------------------------------------------

@admin_router.get("/api/sites/{site_id}/images")
async def list_images(site_id: str):
    site = _get_site(site_id)
    images_path = _images_dir(site)
    captions_path = images_path / "captions.md"
    captions: dict[str, str] = {}
    if captions_path.exists():
        captions = _parse_captions(captions_path.read_text(encoding="utf-8"))
    images = []
    for f in sorted(images_path.iterdir()):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
            images.append({
                "name": f.name,
                "size": f.stat().st_size,
                "extension": f.suffix.lower(),
                "caption": captions.get(f.name, ""),
            })
    return {"images": images}


@admin_router.get("/api/sites/{site_id}/images/{filename}/file")
async def serve_image_file(site_id: str, filename: str):
    """Serve the raw image file (used by admin thumbnails)."""
    site = _get_site(site_id)
    images_path = _images_dir(site)
    full_path = (images_path / filename).resolve()
    if not str(full_path).startswith(str(images_path.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    media_type, _ = mimetypes.guess_type(str(full_path))
    return FileResponse(str(full_path), media_type=media_type or "application/octet-stream")


@admin_router.post("/api/sites/{site_id}/images/upload")
async def upload_image(site_id: str, file: UploadFile = File(...)):
    site = _get_site(site_id)
    images_path = _images_dir(site)
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    suffix = Path(filename).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Not an image file ({suffix})")
    full_path = images_path / filename
    data = await file.read()
    full_path.write_bytes(data)
    return {"status": "ok", "name": filename, "size": len(data)}


@admin_router.delete("/api/sites/{site_id}/images/{filename}")
async def delete_image(site_id: str, filename: str):
    site = _get_site(site_id)
    images_path = _images_dir(site)
    full_path = (images_path / filename).resolve()
    if not str(full_path).startswith(str(images_path.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    full_path.unlink()
    return {"status": "ok", "name": filename}


@admin_router.put("/api/sites/{site_id}/images/{filename}/caption")
async def set_image_caption(site_id: str, filename: str, body: ImageCaptionUpdate):
    site = _get_site(site_id)
    images_path = _images_dir(site)
    captions_path = images_path / "captions.md"
    captions: dict[str, str] = {}
    if captions_path.exists():
        captions = _parse_captions(captions_path.read_text(encoding="utf-8"))
    caption = body.caption.strip()
    if caption:
        captions[filename] = caption
    else:
        captions.pop(filename, None)
    captions_path.write_text(_serialize_captions(captions), encoding="utf-8")
    return {"status": "ok", "name": filename, "caption": caption}


# ---------------------------------------------------------------------------
# Per-site: prompt
# ---------------------------------------------------------------------------

@admin_router.get("/api/sites/{site_id}/prompt")
async def get_prompt(site_id: str):
    site = _get_site(site_id)
    content = ""
    if site.prompt_path.exists():
        content = site.prompt_path.read_text(encoding="utf-8")
    return {"content": content}


@admin_router.put("/api/sites/{site_id}/prompt")
async def set_prompt(site_id: str, body: PromptUpdateRequest):
    site = _get_site(site_id)
    site.prompt_path.write_text(body.content, encoding="utf-8")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Per-site: styles
# ---------------------------------------------------------------------------

@admin_router.get("/api/sites/{site_id}/styles")
async def get_styles(site_id: str):
    site = _get_site(site_id)
    content = ""
    if site.styles_path.exists():
        content = site.styles_path.read_text(encoding="utf-8")
    return {"content": content}


@admin_router.put("/api/sites/{site_id}/styles")
async def set_styles(site_id: str, body: StylesUpdateRequest):
    site = _get_site(site_id)
    site.styles_path.write_text(body.content, encoding="utf-8")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Global runtime settings
# ---------------------------------------------------------------------------

@admin_router.get("/api/settings")
async def get_runtime_settings():
    settings = get_settings()
    return {
        "ai_provider": settings.ai_provider,
        "has_api_key": bool(settings.ai_api_key),
        "ai_model": settings.ai_model,
        "ai_max_tokens": settings.ai_max_tokens,
        "content_mode": settings.content_mode,
        "persist_session": settings.persist_session,
    }


@admin_router.put("/api/settings")
async def set_runtime_settings(body: SettingsUpdateRequest):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided")
    settings = update_settings(**updates)
    reset_ai_services()
    return {
        "ai_provider": settings.ai_provider,
        "has_api_key": bool(settings.ai_api_key),
        "ai_model": settings.ai_model,
        "ai_max_tokens": settings.ai_max_tokens,
        "content_mode": settings.content_mode,
        "persist_session": settings.persist_session,
    }
