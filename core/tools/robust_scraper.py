"""
Robust Web Scraper Tool

A production-ready web scraper using requests and BeautifulSoup with:
- Automatic retries with exponential backoff
- User-Agent rotation
- Session management
- Error handling
- Content cleaning
"""

import logging
import random
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# List of common user agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
]


class RobustScraper:
    """
    A robust web scraper that handles retries, timeouts, and user-agent rotation.
    """

    def __init__(self, retries: int = 3, backoff_factor: float = 0.3, timeout: int = 30):
        """
        Initialize the scraper.

        Args:
            retries: Number of retries for failed requests.
            backoff_factor: Backoff factor for retries.
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout
        self.session = requests.Session()

        # Configure retries
        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _get_headers(self) -> dict[str, str]:
        """Get headers with a random User-Agent."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

    def scrape(self, url: str, extract_air_quality_data: bool = True) -> dict[str, Any]:
        """
        Scrape a URL and return structured data.
        Intelligently extracts air quality data from known providers.

        Args:
            url: The URL to scrape.
            extract_air_quality_data: If True, attempt to extract air quality metrics

        Returns:
            A dictionary containing title, text content, and metadata.
        """
        try:
            logger.info(f"Scraping URL: {url}")
            response = self.session.get(url, headers=self._get_headers(), timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script.decompose()

            # Extract title
            title = "No Title"
            if soup.title and soup.title.string:
                title = soup.title.string.strip()

            # Extract text
            text = soup.get_text(separator="\n", strip=True)

            # Clean up text (remove excessive newlines)
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = "\n".join(chunk for chunk in chunks if chunk)

            # Extract links
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if isinstance(href, list):
                    href = href[0]
                full_url = urljoin(url, str(href))
                links.append({"text": a.get_text(strip=True), "url": full_url})

            result = {
                "url": url,
                "title": title,
                "content": clean_text[:20000],  # Limit content size
                "links": links[:50],  # Limit number of links
                "status_code": response.status_code,
            }

            # Extract air quality data if requested and URL is from known provider
            if extract_air_quality_data:
                air_quality_data = self._extract_air_quality_metrics(soup, url)
                if air_quality_data:
                    result["air_quality_data"] = air_quality_data
                    logger.info(f"Extracted air quality data from {url}")

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Error scraping {url}: {e}")
            return {"error": str(e), "url": url}
        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {e}")
            return {"error": str(e), "url": url}

    def _extract_air_quality_metrics(self, soup: BeautifulSoup, url: str) -> dict[str, Any] | None:
        """
        Extract air quality metrics from known providers (IQAir, PurpleAir, etc.).

        Args:
            soup: BeautifulSoup object of the page
            url: URL being scraped

        Returns:
            Dictionary with extracted AQ metrics or None
        """
        try:
            data = {}

            # IQAir-specific extraction
            if "iqair.com" in url:
                # Look for AQI values in common patterns
                aqi_patterns = [
                    ("aqi-value", "class"),
                    ("aqi-number", "class"),
                    ("aqi", "id"),
                    ("air-quality-value", "class"),
                ]

                for pattern, attr_type in aqi_patterns:
                    if attr_type == "class":
                        element = soup.find(class_=pattern)
                    else:
                        element = soup.find(id=pattern)

                    if element:
                        aqi_text = element.get_text(strip=True)
                        try:
                            data["aqi"] = int("".join(filter(str.isdigit, aqi_text)))
                        except ValueError:
                            pass

                # Extract location
                location_element = soup.find("h1") or soup.find(class_="location-name")
                if location_element:
                    data["location"] = location_element.get_text(strip=True)

                # Extract pollutants (PM2.5, PM10, etc.)
                pollutant_containers = soup.find_all(class_=["pollutant-item", "pollutant-value"])
                for container in pollutant_containers:
                    text = container.get_text(strip=True)
                    if "PM2.5" in text:
                        data["pm2.5"] = text
                    elif "PM10" in text:
                        data["pm10"] = text
                    elif "O3" in text or "Ozone" in text:
                        data["o3"] = text

            # Generic air quality data extraction for other sites
            else:
                # Look for common AQI indicators
                text_lower = soup.get_text().lower()
                if any(
                    keyword in text_lower for keyword in ["aqi", "air quality", "pm2.5", "pm10"]
                ):
                    # Extract any numeric AQI values
                    import re

                    aqi_matches = re.findall(
                        r"\b(?:aqi|air quality index)[:\s]*([0-9]{1,3})\b", text_lower
                    )
                    if aqi_matches:
                        data["aqi"] = int(aqi_matches[0])

            return data if data else None

        except Exception as e:
            logger.warning(f"Error extracting air quality data: {e}")
            return None

    def close(self):
        """Close the session."""
        self.session.close()
