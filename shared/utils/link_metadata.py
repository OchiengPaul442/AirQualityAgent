"""
Link Metadata Extractor for Rich Link Previews
Extracts metadata from URLs to create rich link previews with titles, descriptions, and favicons
"""
import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)


class LinkMetadataExtractor:
    """Extract metadata from URLs for rich link previews"""

    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.cache = {}  # Simple in-memory cache

    def extract_metadata(self, url: str) -> Dict[str, Any]:
        """
        Extract metadata from a URL including title, description, image, and favicon
        
        Args:
            url: The URL to extract metadata from
            
        Returns:
            Dictionary with metadata fields
        """
        # Check cache first
        if url in self.cache:
            return self.cache[url]

        metadata = {
            "url": url,
            "title": self._get_domain_name(url),
            "description": "",
            "image": "",
            "favicon": self._get_default_favicon(url),
            "site_name": self._get_domain_name(url),
        }

        try:
            # Fetch the page
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = httpx.get(url, headers=headers, timeout=self.timeout, follow_redirects=True)

            if response.status_code == 200:
                html = response.text

                # Extract Open Graph metadata
                og_title = self._extract_og_tag(html, "og:title")
                og_description = self._extract_og_tag(html, "og:description")
                og_image = self._extract_og_tag(html, "og:image")
                og_site_name = self._extract_og_tag(html, "og:site_name")

                # Extract Twitter Card metadata as fallback
                twitter_title = self._extract_meta_tag(html, "twitter:title")
                twitter_description = self._extract_meta_tag(html, "twitter:description")
                twitter_image = self._extract_meta_tag(html, "twitter:image")

                # Extract standard HTML metadata
                html_title = self._extract_title(html)
                html_description = self._extract_meta_tag(html, "description")

                # Prioritize metadata sources
                metadata["title"] = og_title or twitter_title or html_title or metadata["title"]
                metadata["description"] = (
                    og_description or twitter_description or html_description or ""
                )
                metadata["image"] = og_image or twitter_image or ""
                metadata["site_name"] = og_site_name or metadata["site_name"]

                # Make image URL absolute
                if metadata["image"] and not metadata["image"].startswith("http"):
                    metadata["image"] = urljoin(url, metadata["image"])

                # Try to find favicon
                favicon = self._extract_favicon(html, url)
                if favicon:
                    metadata["favicon"] = favicon

        except Exception as e:
            logger.warning(f"Failed to extract metadata from {url}: {e}")

        # Cache the result
        self.cache[url] = metadata
        return metadata

    def _extract_og_tag(self, html: str, property_name: str) -> str:
        """Extract Open Graph meta tag"""
        pattern = f'<meta\\s+property=["\']({property_name})["\']\\s+content=["\']([^"\']+)["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(2)

        # Try alternate format
        pattern = f'<meta\\s+content=["\']([^"\']+)["\']\\s+property=["\']({property_name})["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        return match.group(1) if match else ""

    def _extract_meta_tag(self, html: str, name: str) -> str:
        """Extract standard meta tag"""
        pattern = f'<meta\\s+name=["\']({name})["\']\\s+content=["\']([^"\']+)["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(2)

        # Try alternate format
        pattern = f'<meta\\s+content=["\']([^"\']+)["\']\\s+name=["\']({name})["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        return match.group(1) if match else ""

    def _extract_title(self, html: str) -> str:
        """Extract HTML title tag"""
        match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_favicon(self, html: str, base_url: str) -> str:
        """Extract favicon URL from HTML"""
        # Look for link rel="icon" or rel="shortcut icon"
        patterns = [
            r'<link\s+[^>]*rel=["\'](?:shortcut )?icon["\'][^>]*href=["\']([^"\']+)["\']',
            r'<link\s+[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\'](?:shortcut )?icon["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                favicon_url = match.group(1)
                if not favicon_url.startswith("http"):
                    favicon_url = urljoin(base_url, favicon_url)
                return favicon_url

        return self._get_default_favicon(base_url)

    def _get_default_favicon(self, url: str) -> str:
        """Get default favicon URL for a domain"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"

    def _get_domain_name(self, url: str) -> str:
        """Extract clean domain name from URL"""
        parsed = urlparse(url)
        domain = parsed.netloc
        # Remove www. prefix
        domain = re.sub(r'^www\.', '', domain)
        # Capitalize first letter
        return domain.split('.')[0].capitalize()

    def format_rich_link(self, url: str, link_text: Optional[str] = None) -> str:
        """
        Format a URL as a rich markdown link with metadata
        
        Args:
            url: The URL to format
            link_text: Optional custom link text (defaults to extracted title)
            
        Returns:
            Markdown formatted rich link
        """
        metadata = self.extract_metadata(url)

        display_text = link_text or metadata["title"]

        # Create rich markdown with hover preview
        # Format: [Text](URL "Title - Description")
        hover_text = metadata["title"]
        if metadata["description"]:
            # Truncate description to 150 chars
            desc = metadata["description"][:150]
            if len(metadata["description"]) > 150:
                desc += "..."
            hover_text += f" - {desc}"

        return f'[{display_text}]({url} "{hover_text}")'


# Global instance
_link_extractor = None

def get_link_extractor() -> LinkMetadataExtractor:
    """Get global link metadata extractor instance"""
    global _link_extractor
    if _link_extractor is None:
        _link_extractor = LinkMetadataExtractor()
    return _link_extractor
