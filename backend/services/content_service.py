"""
Content Service for infinidom Framework

Loads content from a site's content folder for AI context.
"""
from pathlib import Path
from typing import Optional
import aiofiles

from backend.services.site_loader import Site

# Text file extensions we read for AI context
TEXT_EXTENSIONS = {'.md', '.txt', '.json', '.yaml', '.yml'}


class ContentService:
    """
    Loads content for a specific site.
    
    Each site has its own content folder where users can place any files:
    - Text files (.md, .txt, .json, .yaml) are read and provided to the AI
    - Image files can be placed directly or in subfolders
    - The folder structure is flexible - users organize as they prefer
    """
    
    def __init__(self, site: Site):
        self.site = site
        self._cache: dict[str, str] = {}
    
    async def get_all_content(self) -> str:
        """Get all text content from the site's content folder."""
        content_path = self.site.content_path
        
        if not content_path.exists():
            return ""
        
        contents = []
        for file_path in sorted(content_path.rglob("*")):
            if file_path.is_file() and not file_path.name.startswith('.'):
                # Only read text files
                if file_path.suffix.lower() in TEXT_EXTENSIONS:
                    content = await self._read_file(file_path)
                    if content:
                        # Use relative path from content folder for better context
                        rel_path = file_path.relative_to(content_path)
                        contents.append(f"### {rel_path}\n{content}")
        
        return "\n\n---\n\n".join(contents)
    
    async def get_site_prompt(self) -> str:
        """Get the site's custom prompt instructions."""
        prompt_path = self.site.prompt_path
        
        if prompt_path.exists():
            async with aiofiles.open(prompt_path, 'r') as f:
                return await f.read()
        return ""
    
    async def get_relevant_content(self, event: dict) -> str:
        """
        Get content relevant to the current event.
        
        For now returns all content. Could be enhanced with
        semantic search or keyword matching in the future.
        """
        all_content = await self.get_all_content()
        
        if not all_content:
            return f"No content available for {self.site.name}. Generate reasonable default content."
        
        return all_content
    
    async def _read_file(self, path: Path) -> Optional[str]:
        """Read a file with caching."""
        cache_key = str(path)
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                content = await f.read()
                self._cache[cache_key] = content
                return content
        except Exception as e:
            print(f"Error reading {path}: {e}")
            return None
