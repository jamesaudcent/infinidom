"""Admin routes for managing site content and runtime settings."""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.config import get_settings, update_settings
from backend.defaults import _parse_captions, _serialize_captions
from backend.services.ai_service import reset_ai_services
from backend.services.site_loader import get_site_loader


admin_router = APIRouter(prefix="/admin")
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".css", ".html", ".js"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"}


class SiteUpdateRequest(BaseModel):
    name: Optional[str] = None
    theme: Optional[str] = None


class ContentUpdateRequest(BaseModel):
    content: str


class PromptUpdateRequest(BaseModel):
    content: str


class StylesUpdateRequest(BaseModel):
    content: str


class SettingsUpdateRequest(BaseModel):
    ai_provider: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None
    ai_max_tokens: Optional[int] = None
    content_mode: Optional[str] = None
    persist_session: Optional[bool] = None


def get_site_or_404(request: Request):
    site = getattr(request.state, "site", None)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found for this domain")
    return site


def _resolve_content_path(base_path: Path, relative_path: str) -> Path:
    candidate = (base_path / relative_path).resolve()
    base_resolved = base_path.resolve()
    if not str(candidate).startswith(str(base_resolved)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    return candidate


# ---------------------------------------------------------------------------
# Admin HTML
# ---------------------------------------------------------------------------

@admin_router.get("")
@admin_router.get("/")
async def serve_admin():
    admin_path = Path(__file__).parent.parent.parent / "frontend" / "admin.html"
    if not admin_path.exists():
        raise HTTPException(status_code=404, detail="Admin UI not found")
    return FileResponse(str(admin_path), media_type="text/html")


# ---------------------------------------------------------------------------
# Site config
# ---------------------------------------------------------------------------

@admin_router.get("/api/site")
async def get_site_info(request: Request):
    site = get_site_or_404(request)
    return {
        "id": site.id,
        "name": site.name,
        "theme": site.theme,
        "domains": site.domains,
    }


@admin_router.put("/api/site")
async def update_site_info(request: Request, body: SiteUpdateRequest):
    site = get_site_or_404(request)
    if body.name is None and body.theme is None:
        raise HTTPException(status_code=400, detail="No fields provided")

    loader = get_site_loader()
    updated = loader.update_site_config(site.id, name=body.name, theme=body.theme)
    if not updated:
        raise HTTPException(status_code=404, detail="Site config not found")

    return {
        "id": updated.id,
        "name": updated.name,
        "theme": updated.theme,
        "domains": updated.domains,
    }


# ---------------------------------------------------------------------------
# Content files (text only, excludes images/ subfolder)
# ---------------------------------------------------------------------------

@admin_router.get("/api/content")
async def list_content_files(request: Request):
    site = get_site_or_404(request)
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


@admin_router.get("/api/content/{filepath:path}")
async def read_content_file(request: Request, filepath: str):
    site = get_site_or_404(request)
    full_path = _resolve_content_path(site.content_path, filepath)
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    suffix = full_path.suffix.lower()
    if suffix not in TEXT_EXTENSIONS:
        return {"path": filepath, "is_text": False, "content": None}

    return {"path": filepath, "is_text": True, "content": full_path.read_text(encoding="utf-8")}


@admin_router.put("/api/content/{filepath:path}")
async def write_content_file(request: Request, filepath: str, body: ContentUpdateRequest):
    site = get_site_or_404(request)
    full_path = _resolve_content_path(site.content_path, filepath)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(body.content, encoding="utf-8")
    return {"status": "ok", "path": filepath}


@admin_router.delete("/api/content/{filepath:path}")
async def delete_content_file(request: Request, filepath: str):
    site = get_site_or_404(request)
    full_path = _resolve_content_path(site.content_path, filepath)
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    full_path.unlink()
    return {"status": "ok", "path": filepath}


# ---------------------------------------------------------------------------
# Images (content/images/)
# ---------------------------------------------------------------------------

def _images_dir(request: Request) -> Path:
    site = get_site_or_404(request)
    d = site.content_path / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d


@admin_router.get("/api/images")
async def list_images(request: Request):
    images_path = _images_dir(request)
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


@admin_router.post("/api/images/upload")
async def upload_image(request: Request, file: UploadFile = File(...)):
    images_path = _images_dir(request)
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


@admin_router.delete("/api/images/{filename}")
async def delete_image(request: Request, filename: str):
    images_path = _images_dir(request)
    full_path = (images_path / filename).resolve()
    if not str(full_path).startswith(str(images_path.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    full_path.unlink()
    return {"status": "ok", "name": filename}


class ImageCaptionUpdate(BaseModel):
    caption: str


@admin_router.put("/api/images/{filename}/caption")
async def set_image_caption(request: Request, filename: str, body: ImageCaptionUpdate):
    images_path = _images_dir(request)
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
# Prompt
# ---------------------------------------------------------------------------

@admin_router.get("/api/prompt")
async def get_prompt(request: Request):
    site = get_site_or_404(request)
    content = ""
    if site.prompt_path.exists():
        content = site.prompt_path.read_text(encoding="utf-8")
    return {"content": content}


@admin_router.put("/api/prompt")
async def set_prompt(request: Request, body: PromptUpdateRequest):
    site = get_site_or_404(request)
    site.prompt_path.write_text(body.content, encoding="utf-8")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

@admin_router.get("/api/styles")
async def get_styles(request: Request):
    site = get_site_or_404(request)
    content = ""
    if site.styles_path.exists():
        content = site.styles_path.read_text(encoding="utf-8")
    return {"content": content}


@admin_router.put("/api/styles")
async def set_styles(request: Request, body: StylesUpdateRequest):
    site = get_site_or_404(request)
    site.styles_path.write_text(body.content, encoding="utf-8")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Runtime settings
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
