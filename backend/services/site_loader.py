"""
Site Loader for infinidom Framework

Loads site configurations and resolves domains to site folders.
"""
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import yaml


@dataclass
class Site:
    """Represents a site configuration."""
    id: str
    path: Path
    name: str
    domains: list[str]
    theme: str = "light"
    
    @property
    def content_path(self) -> Path:
        """Path to the site's content folder (text, images, any assets)."""
        return self.path / "content"
    
    @property
    def prompt_path(self) -> Path:
        return self.path / "prompt.txt"
    
    @property
    def styles_path(self) -> Path:
        """Path to the site's custom styles.css file."""
        return self.path / "styles.css"


class SiteLoader:
    """Loads and manages site configurations."""
    
    def __init__(self, sites_path: Path = None):
        self.sites_path = sites_path or Path(__file__).parent.parent.parent / "sites"
        self._sites: dict[str, Site] = {}
        self._domain_map: dict[str, str] = {}
        self._load_config()
    
    def _load_config(self):
        """Load sites from config.yaml."""
        config_path = self.sites_path / "config.yaml"
        self._sites = {}
        self._domain_map = {}
        
        if not config_path.exists():
            return
        
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        
        # Load defaults
        defaults = config.get("defaults", {})
        default_theme = defaults.get("theme", "light")
        
        for site_id, site_config in config.get("sites", {}).items():
            site = Site(
                id=site_id,
                path=self.sites_path / site_id,
                name=site_config.get("name", site_id),
                domains=site_config.get("domains", []),
                theme=site_config.get("theme", default_theme)
            )
            self._sites[site_id] = site
            
            # Map each domain to its site
            for domain in site.domains:
                self._domain_map[domain.lower()] = site_id

    def reload(self):
        """Reload site configuration from disk."""
        self._load_config()

    def update_site_config(
        self,
        site_id: str,
        *,
        name: Optional[str] = None,
        theme: Optional[str] = None
    ) -> Optional[Site]:
        """Update mutable site config fields and reload state."""
        config_path = self.sites_path / "config.yaml"
        if not config_path.exists():
            return None

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        sites = config.get("sites", {})
        if site_id not in sites:
            return None

        site_config = sites[site_id] or {}
        if name is not None:
            site_config["name"] = name
        if theme is not None:
            site_config["theme"] = theme
        sites[site_id] = site_config
        config["sites"] = sites

        with open(config_path, "w") as f:
            yaml.safe_dump(config, f, sort_keys=False)

        self.reload()
        return self.get_site(site_id)
    
    def get_site_by_domain(self, domain: str) -> Optional[Site]:
        """Find site matching the given domain."""
        domain = domain.lower().split(":")[0]  # Remove port if present
        site_id = self._domain_map.get(domain)
        return self._sites.get(site_id) if site_id else None
    
    def get_site(self, site_id: str) -> Optional[Site]:
        """Get site by ID."""
        return self._sites.get(site_id)
    
    def list_sites(self) -> list[Site]:
        """List all configured sites."""
        return list(self._sites.values())


# Global instance
_site_loader: Optional[SiteLoader] = None


def get_site_loader() -> SiteLoader:
    """Get the global site loader instance."""
    global _site_loader
    if _site_loader is None:
        _site_loader = SiteLoader()
    return _site_loader
