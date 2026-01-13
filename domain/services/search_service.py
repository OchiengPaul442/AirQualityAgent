import json
import logging
import os
import time
from typing import Any, Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

try:
    from ddgs import DDGS  # type: ignore
except ImportError:
    try:
        from duckduckgo_search import DDGS  # type: ignore
    except ImportError:
        logger.warning("DuckDuckGo search libraries not available. Search functionality will be limited.")
        DDGS = None  # type: ignore


class SearchService:
    """
    Enhanced service for performing web searches using multiple providers.
    Supports DuckDuckGo, and fallback mechanisms for air quality and environmental information.
    """

    # Trusted air quality and environmental sources
    # Comprehensive international directory of air quality monitoring websites
    # Updated with global, regional, and government sources for maximum coverage
    TRUSTED_SOURCES = [
        # GLOBAL DATA AGGREGATORS & PLATFORMS
        "openaq.org",           # Non-profit, aggregates 500+ global sources
        "stateofglobalair.org", # Health Effects Institute, global data
        "earthdata.nasa.gov",   # Satellite data
        "iqair.com",            # Real-time global map
        "aqicn.org",            # Global monitoring network (WAQI)
        "waqi.info",            # World Air Quality Index
        "who.int",              # WHO Global Air Quality
        "eea.europa.eu",        # European Environment Agency
        "airindex.eea.europa.eu", # European Air Quality Index
        "atmosphere.copernicus.eu", # Copernicus Atmosphere Monitoring
        "airbase.eea.europa.eu", # AirBase Database

        # AFRICA - Regional Networks
        "cleanairafrica.org",   # CLEAN-Air Africa (NIHR)
        "africancleanair.org",  # Africa Clean Air Network

        # AFRICA - Government Agencies (Enhanced)
        "nea.gm",               # Gambia: National Environment Agency
        "nema.go.ug",           # Uganda: NEMA (AirQo partnership)
        "nema.go.ke",           # Kenya: NEMA
        "nairobi.go.ke",        # Nairobi City County Government
        "meteo.go.ke",          # Kenya Meteorological Department
        "environment.gov.za",   # South Africa: Department of Environment
        "saaqis.environment.gov.za", # South African Air Quality Information System
        "lasepa.gov.ng",        # Lagos State Environmental Protection Agency
        "nesrea.gov.ng",        # Nigeria: NESREA
        "environment.gov.ng",   # Nigeria: Federal Ministry of Environment
        "epa.gov.gh",           # Ghana EPA
        "meteo.gov.ma",         # Morocco: Meteorology Service
        "eeaa.gov.eg",          # Egypt: Egyptian Environmental Affairs Agency
        "saaois.org.za",        # South Africa: SAAQIS
        "vpo.go.tz",            # Tanzania: Vice President's Office - Environment
        "rema.gov.rw",          # Rwanda: Rwanda Environment Management Authority
        "environnement.gouv.sn", # Senegal: Ministère de l'Environnement

        # AFRICA - NGOs & Research (Enhanced)
        "airqo.net",            # AirQo Uganda-based network
        "airqo.africa",         # AirQo Africa
        "airqo.net/explore",    # AirQo Network Map
        "airqo.net/explore-data", # AirQo Explore Data
        "airqo.africa/products/api", # AirQo API
        "sei.org",              # SEI Africa (Nairobi, Kampala, Addis Ababa)
        "cleanairafrica.org",   # CLEAN-Air Africa (NIHR)
        "cleanairafrica.org/events", # CLEAN-Air Africa Events
        "afriqair.cmu.edu",     # AfriqAir — African Air Quality Monitoring Network
        "cmu.edu/epp/afriqair", # Carnegie Mellon AfriqAir

        # AFRICA - Data Platforms & Archives
        "openafrica.net",       # Open Africa datasets
        "bulk.openafrica.net",  # sensors.AFRICA Archive
        "odza.opendata.durban", # Durban Open Data (SAAQIS)
        "air-quality.com/continent/africa", # Air Matters Africa
        "greenpeace.org/africa", # Greenpeace Africa
        "energyandcleanair.org/region/africa", # CREA Africa Reports
        "unep.org/explore-topics/air", # UNEP Africa Air Quality

        # ASIA - Regional Networks
        "asic.aqrc.ucdavis.edu", # Southeast Asia: ASIC Network
        "gov.hk",               # Pearl River Delta Network (China/Hong Kong/Macau)

        # ASIA - Government Agencies (China)
        "mee.gov.cn",           # China: Ministry of Ecology & Environment
        "cnemc.cn",             # China National Environmental Monitoring Centre

        # ASIA - Government Agencies (India)
        "cpcb.nic.in",          # India: Central Pollution Control Board
        "app.cpcbccr.com",      # India: National Air Quality Index

        # ASIA - Government Agencies (South Korea)
        "me.go.kr",             # South Korea: Ministry of Environment
        "keco.or.kr",           # South Korea: Korea Environment Corporation

        # ASIA - Government Agencies (Japan)
        "env.go.jp",            # Japan: Ministry of Environment
        "soramame.taiki.go.jp", # Japan: Atmospheric Environmental Regional Observation

        # ASIA - Government Agencies (Southeast Asia)
        "nea.gov.sg",           # Singapore: NEA (PSI readings)
        "pcd.go.th",            # Thailand: Pollution Control Department
        "menlhk.go.id",         # Indonesia: Ministry of Environment
        "doe.gov.my",           # Malaysia: Department of Environment
        "denr.gov.ph",          # Philippines: DENR

        # ASIA - Hong Kong & Taiwan
        "epd.gov.hk",           # Hong Kong EPD (Air Quality Health Index)
        "epa.gov.tw",           # Taiwan EPA

        # EUROPE - Government Agencies
        "umweltbundesamt.de",   # Germany: UBA
        "atmo-france.org",      # France: Atmo
        "defra.gov.uk",         # UK: DEFRA
        "rivm.nl",              # Netherlands: RIVM
        "miteco.gob.es",        # Spain: MITECO
        "isprambiente.gov.it",  # Italy: ISPRA

        # NORTH AMERICA - United States
        "airnow.gov",           # EPA AirNow (Real-time AQI)
        "aqs.epa.gov",          # EPA AirData
        "cdc.gov",              # CDC Air Quality
        "arb.ca.gov",           # California ARB
        "tceq.texas.gov",       # Texas TCEQ

        # NORTH AMERICA - Canada
        "canada.ca",            # Environment & Climate Change Canada
        "weather.gc.ca",        # Air Quality Health Index
        "gov.bc.ca",            # British Columbia
        "ontario.ca",           # Ontario

        # NORTH AMERICA - Mexico
        "gob.mx",               # SEMARNAT
        "aire.cdmx.gob.mx",     # Mexico City Air Quality

        # SOUTH AMERICA - Government Agencies
        "gov.br",               # Brazil: IBAMA
        "cetesb.sp.gov.br",     # Brazil: CETESB (São Paulo)
        "mma.gob.cl",           # Chile: MMA
        "sinca.mma.gob.cl",     # Chile: SINCA
        "argentina.gob.ar",     # Argentina: Ministry of Environment
        "ideam.gov.co",         # Colombia: IDEAM
        "senamhi.gob.pe",       # Peru: SENAMHI

        # AUSTRALIA & OCEANIA
        "dceew.gov.au",         # DCCEEW Air Quality
        "mfe.govt.nz",          # New Zealand: Ministry for the Environment

        # AUSTRALIA - State Portals
        "dpi.nsw.gov.au",       # NSW
        "epa.vic.gov.au",       # Victoria
        "qld.gov.au",           # Queensland
        "wa.gov.au",            # Western Australia
        "act.gov.au",           # ACT Government

        # KEY NGO & RESEARCH NETWORKS
        "healtheffects.org",    # Health Effects Institute
        "ccacoalition.org",     # Climate & Clean Air Coalition
        "cleanairfund.org",     # Clean Air Fund
        "unep.org",             # UNEP Air Quality
        "worldbank.org",        # World Bank Air Quality
        "nature.com",           # Nature (Research)
        "sciencedirect.com",    # ScienceDirect
        "nih.gov",              # NIH
        "icraq.org",            # International Clinical Research

        # Additional platforms from original list
        "open-meteo.com",
        "carbonintensity.org.uk",
        "breezometer.com",
        "purpleair.com",
        "airgradient.com",
        "osf.io",
        "uneca.org",
        "airquality.gov",
        "nesrea.gov.ng",
        "airquality.nsw.gov.au",
        "copernicus.eu",
        "worldview.earthdata.nasa.gov",
        "ciesin.columbia.edu",
        "sedac.ciesin.columbia.edu",
        "ecmwf.int",
        "afdb.org",
        "dataportal.afdb.org",
    ]

    def __init__(self):
        """Initialize search service with multiple providers."""
        self.providers = {
            "duckduckgo": self._search_duckduckgo,
            "dashscope": self._search_dashscope,
        }
        self.default_provider = "duckduckgo"

    def search(
        self, query: str, max_results: int = 5, provider: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Performs a web search using the specified provider or default provider.
        Returns a list of search results with 'title', 'href', and 'body' fields.

        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 5)
            provider: Search provider to use (default: duckduckgo)

        Returns:
            List of search result dictionaries with title, href, and body
        """
        provider_name = provider or self.default_provider

        if provider_name not in self.providers:
            logger.warning(
                f"Unknown provider '{provider_name}', falling back to {self.default_provider}"
            )
            provider_name = self.default_provider

        # Try the primary provider
        try:
            results = self.providers[provider_name](query, max_results)
            if results and len(results) > 0:
                # Prioritize trusted sources
                results = self._prioritize_trusted_sources(results)
                logger.info(
                    f"Found {len(results)} search results for query: {query} using {provider_name}"
                )
                return results
        except Exception as e:
            logger.error(f"Error with provider {provider_name}: {e}")

        # Fallback to other providers if available
        for fallback_provider, search_func in self.providers.items():
            if fallback_provider == provider_name:
                continue
            try:
                logger.info(f"Trying fallback provider: {fallback_provider}")
                results = search_func(query, max_results)
                if results and len(results) > 0:
                    results = self._prioritize_trusted_sources(results)
                    logger.info(
                        f"Found {len(results)} search results using fallback provider {fallback_provider}"
                    )
                    return results
            except Exception as e:
                logger.error(f"Fallback provider {fallback_provider} also failed: {e}")

        # All providers failed
        logger.error(f"All search providers failed for query: {query}")
        return [
            {
                "title": "Search Unavailable",
                "body": "All search providers are currently unavailable. Please try again later or contact support.",
                "href": "",
            }
        ]

    def _search_duckduckgo(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """
        Robust DuckDuckGo search with best practices for reliability.

        Features:
        - Simplified, reliable search execution
        - Proper timeout management
        - Graceful error handling and fallbacks
        - Credibility assessment and source prioritization
        - No complex concurrent operations that can cause timeouts

        Returns results with: title, href, body, and enhanced metadata
        """
        # Check if DDGS is available
        if DDGS is None:
            logger.warning("DuckDuckGo search not available - library not installed")
            return []

        try:
            # Simple, reliable search execution
            max_retries = 3
            raw_results = []

            for attempt in range(max_retries):
                try:
                    # Use a single DDGS instance with reasonable timeout
                    with DDGS() as ddgs:
                        # Simple search - let DDGS handle the complexity
                        results = list(ddgs.text(query, max_results=max_results * 2, timelimit=10.0))
                        if results:
                            raw_results = results
                            break

                    # If we get here without results, wait before retry
                    if attempt < max_retries - 1:
                        logger.info(f"DuckDuckGo search attempt {attempt + 1} returned no results, retrying...")
                        time.sleep(2 ** attempt)  # Exponential backoff

                except Exception as e:
                    logger.warning(f"DuckDuckGo search attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        logger.error(f"All DuckDuckGo search attempts failed for query: {query}")
                        return []

            if not raw_results:
                logger.warning(f"No search results found for query: {query}")
                return []

            # Enhanced filtering and quality assessment
            filtered_results = []
            seen_urls = set()
            domain_counts = {}  # Track source diversity

            for result in raw_results:
                href = result.get("href", "").strip()
                title = result.get("title", "").strip()
                body = result.get("body", "").strip()

                # Skip if essential fields missing
                if not href or not title or not body:
                    continue

                # Skip duplicates
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # Quality filters
                if len(body) < 30 or len(title) < 5:
                    continue  # Too short content

                # Skip obvious ads/low-quality content
                if any(phrase in title.lower() for phrase in ['buy now', 'best price', 'sponsored', 'advertisement']):
                    continue

                # Track domain diversity (max 2 results per domain)
                domain = self._extract_domain(href)
                if domain not in domain_counts:
                    domain_counts[domain] = 0
                if domain_counts[domain] >= 2:
                    continue
                domain_counts[domain] += 1

                filtered_results.append(result)

            # Sort by quality and credibility
            scored_results = []
            for idx, result in enumerate(filtered_results):
                score = self._calculate_result_score(result, idx)
                result['_quality_score'] = score
                scored_results.append((score, result))

            scored_results.sort(key=lambda x: x[0], reverse=True)
            top_results = [result for _, result in scored_results[:max_results]]

            # Enhance results with metadata
            enhanced_results = []
            for idx, result in enumerate(top_results):
                href = result.get("href", "").strip()
                domain = self._extract_domain(href)
                is_trusted = self._is_trusted_source(href)

                # Determine source credibility level
                credibility = self._assess_source_credibility(href, domain)

                enhanced = {
                    "title": result.get("title", "").strip(),
                    "href": href,
                    "body": result.get("body", "").strip(),
                    "metadata": {
                        "source": domain,
                        "relevance_rank": idx + 1,
                        "is_trusted": is_trusted,
                        "credibility_level": credibility['level'],
                        "credibility_reason": credibility['reason'],
                        "source_type": result.get('_source_type', 'general'),
                        "quality_score": result.get('_quality_score', 0),
                        "snippet_length": len(result.get("body", "")),
                        "query": query,
                        "search_provider": "duckduckgo",
                        "search_timestamp": time.time(),
                        "total_sources_searched": len(domain_counts),
                    },
                }
                enhanced_results.append(enhanced)

            logger.info(f"✓ DuckDuckGo search returned {len(enhanced_results)} high-quality results from {len(domain_counts)} diverse sources")
            return enhanced_results

        except Exception as e:
            logger.error(f"DuckDuckGo search failed for '{query}': {e}", exc_info=True)
            return []

            # Sort by quality and credibility
            scored_results = []
            for idx, result in enumerate(filtered_results):
                score = self._calculate_result_score(result, idx)
                result['_quality_score'] = score
                scored_results.append((score, result))

            scored_results.sort(key=lambda x: x[0], reverse=True)
            top_results = [result for _, result in scored_results[:max_results]]

            # Enhance results with metadata
            enhanced_results = []
            for idx, result in enumerate(top_results):
                href = result.get("href", "").strip()
                domain = self._extract_domain(href)
                is_trusted = self._is_trusted_source(href)

                # Determine source credibility level
                credibility = self._assess_source_credibility(href, domain)

                enhanced = {
                    "title": result.get("title", "").strip(),
                    "href": href,
                    "body": result.get("body", "").strip(),
                    "metadata": {
                        "source": domain,
                        "relevance_rank": idx + 1,
                        "is_trusted": is_trusted,
                        "credibility_level": credibility['level'],
                        "credibility_reason": credibility['reason'],
                        "source_type": result.get('_source_type', 'general'),
                        "quality_score": result.get('_quality_score', 0),
                        "snippet_length": len(result.get("body", "")),
                        "query": query,
                        "search_provider": "duckduckgo",
                        "search_timestamp": time.time(),
                        "total_sources_searched": len(domain_counts),
                    },
                }
                enhanced_results.append(enhanced)

            logger.info(f"✓ DuckDuckGo search returned {len(enhanced_results)} high-quality results from {len(domain_counts)} diverse sources")
            return enhanced_results

        except Exception as e:
            logger.error(f"DuckDuckGo search failed for '{query}': {e}", exc_info=True)
            return []

    def _search_dashscope(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """
        Search using DashScope (Alibaba Cloud) web search via Qwen model with function calling.
        
        This method uses the Qwen model with built-in web_search tool to perform internet searches.
        Returns results with: title, href, body, and metadata.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 5)
            
        Returns:
            List of search result dictionaries with title, href, and body
        """
        try:
            # Check if DashScope is available
            try:
                from http import HTTPStatus

                import dashscope
                from dashscope import Generation
            except ImportError:
                logger.error("DashScope SDK not installed. Install with: pip install dashscope")
                raise ImportError("DashScope SDK not installed")

            # Get API key from environment
            api_key = os.getenv("DASHSCOPE_API_KEY", "")
            if not api_key:
                logger.warning("DASHSCOPE_API_KEY not set, skipping DashScope search")
                raise ValueError("DASHSCOPE_API_KEY not configured")

            # Set API key
            dashscope.api_key = api_key

            # Define the web_search tool for Qwen to use
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search the internet for current information about any topic.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query to look up on the internet"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            ]

            # Create a message that will trigger the web search
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that can search the internet. When asked to search, use the web_search tool to find current information."
                },
                {
                    "role": "user",
                    "content": f"Search the internet for: {query}. Provide {max_results} relevant results with titles, URLs, and descriptions."
                }
            ]

            logger.info(f"Initiating DashScope web search for: {query}")

            # Call Qwen model with tools
            response = Generation.call(
                model="qwen-plus",  # Use qwen-plus for better tool calling
                messages=messages,
                tools=tools,
                result_format="message"
            )

            # Check response status
            if response.status_code != HTTPStatus.OK:
                logger.error(f"DashScope API error: {response.code} - {response.message}")
                raise Exception(f"DashScope API error: {response.message}")

            # Parse the response
            results = []

            # Check if the model made tool calls
            if hasattr(response.output, 'choices') and len(response.output.choices) > 0:
                choice = response.output.choices[0]
                message = choice.message

                # Check for tool calls in the response
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        if tool_call.function.name == "web_search":
                            # The tool_call contains the search results
                            # Parse the arguments which may contain results
                            try:
                                tool_result = json.loads(tool_call.function.arguments)
                                logger.info(f"DashScope tool call result: {tool_result}")
                            except json.JSONDecodeError:
                                logger.warning("Could not parse tool call arguments")

                # Get the text content which contains the search results
                if hasattr(message, 'content') and message.content:
                    content = message.content

                    # Parse the content to extract search results
                    # The model returns formatted text with search results
                    # We'll create structured results from the text response

                    # For now, create a single comprehensive result
                    # In production, you may want to parse this more carefully
                    results.append({
                        "title": f"DashScope Search Results for: {query}",
                        "href": "https://dashscope.aliyuncs.com",
                        "body": content,
                        "metadata": {
                            "source": "dashscope",
                            "relevance_rank": 1,
                            "is_trusted": True,
                            "snippet_length": len(content),
                            "query": query,
                            "provider": "DashScope/Qwen"
                        }
                    })

            # If we got results from DashScope
            if results:
                logger.info(f"DashScope search returned {len(results)} results")
                return results[:max_results]
            else:
                logger.warning(f"No results from DashScope for query: {query}")
                return []

        except ImportError as e:
            logger.error(f"DashScope SDK import error: {e}")
            raise
        except ValueError as e:
            logger.warning(f"DashScope configuration error: {e}")
            raise
        except Exception as e:
            logger.error(f"DashScope search failed for '{query}': {e}")
            raise

    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL."""
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return "unknown"

    def _is_trusted_source(self, url: str) -> bool:
        """Check if URL is from a trusted source."""
        return any(source in url for source in self.TRUSTED_SOURCES)

    def _prioritize_trusted_sources(self, results: list[dict]) -> list[dict]:
        """
        Reorder search results to prioritize trusted environmental and health sources.

        Args:
            results: List of search result dictionaries

        Returns:
            Reordered list with trusted sources first
        """
        trusted = []
        other = []

        for result in results:
            href = result.get("href", "")
            if any(source in href for source in self.TRUSTED_SOURCES):
                trusted.append(result)
            else:
                other.append(result)

        # Return trusted sources first, then others
        return trusted + other

    def _calculate_result_score(self, result: dict, position: int) -> float:
        """
        Calculate a quality score for search result based on multiple factors.

        Args:
            result: Search result dictionary
            position: Original position in results

        Returns:
            Quality score (higher is better)
        """
        score = 0.0
        href = result.get("href", "")
        title = result.get("title", "")
        body = result.get("body", "")

        # Position bonus (earlier results get higher scores)
        score += max(0, 10 - position)

        # Trusted source bonus
        if self._is_trusted_source(href):
            score += 15

        # High priority from site-specific search
        if result.get('_high_priority'):
            score += 10

        # Research/academic content bonus
        if result.get('_source_type') == 'research':
            score += 8

        # Content quality indicators
        if len(body) > 200:
            score += 5
        elif len(body) > 100:
            score += 3

        # Title quality
        if len(title) > 20 and not title.isupper():
            score += 3

        # Domain authority indicators
        domain = self._extract_domain(href)
        if any(gov in domain for gov in ['.gov', '.gov.', 'eea.europa.eu', 'who.int']):
            score += 12  # Government/official sources
        elif any(org in domain for org in ['.org', '.edu', 'unep.org', 'worldbank.org']):
            score += 8   # International organizations
        elif any(academic in domain for academic in ['.edu', '.ac.', 'nature.com', 'sciencedirect.com']):
            score += 6   # Academic sources

        # Penalize potentially low-quality sources
        if any(low_quality in domain for low_quality in ['blogspot', 'wordpress.com', 'medium.com']):
            score -= 5

        return score

    def _assess_source_credibility(self, url: str, domain: str) -> dict:
        """
        Assess the credibility level of a source with detailed reasoning.

        Args:
            url: Full URL
            domain: Extracted domain

        Returns:
            Dict with 'level' and 'reason' keys
        """
        # Government and international organizations - highest credibility
        if any(gov in domain for gov in ['.gov', '.gov.', 'eea.europa.eu', 'copernicus.eu']):
            return {
                'level': 'Official/Government',
                'reason': 'Official government environmental agency or international organization'
            }
        elif domain in ['who.int', 'unep.org', 'worldbank.org', 'un.org']:
            return {
                'level': 'International Organization',
                'reason': 'United Nations or major international environmental organization'
            }

        # Research and academic institutions
        elif any(academic in domain for academic in ['.edu', '.ac.', 'nature.com', 'sciencedirect.com', 'nih.gov', 'cdc.gov']):
            return {
                'level': 'Research/Academic',
                'reason': 'University, research institution, or peer-reviewed publication'
            }

        # Environmental NGOs and networks
        elif any(ngo in domain for ngo in ['cleanairafrica.org', 'airqo.net', 'healtheffects.org', 'ccacoalition.org']):
            return {
                'level': 'Environmental NGO',
                'reason': 'Established environmental non-governmental organization'
            }

        # Commercial air quality platforms
        elif domain in ['iqair.com', 'aqicn.org', 'waqi.info', 'openaq.org']:
            return {
                'level': 'Data Platform',
                'reason': 'Established air quality data aggregation platform'
            }

        # Regional environmental agencies
        elif any(regional in domain for regional in ['.eea.europa.eu', 'defra.gov.uk', 'epa.gov', 'airnow.gov']):
            return {
                'level': 'Regional Authority',
                'reason': 'Regional or national environmental authority'
            }

        # Other trusted sources from our list
        elif self._is_trusted_source(url):
            return {
                'level': 'Trusted Source',
                'reason': 'Verified environmental monitoring organization'
            }

        # Unknown or general sources
        else:
            return {
                'level': 'General Source',
                'reason': 'General web source - verify information independently'
            }

    def scrape_realtime_data(self, url: str, timeout: int = 15) -> Optional[dict]:
        """
        Scrape real-time data from air quality websites with best practices.

        Features:
        - Proper User-Agent rotation to avoid blocking
        - Rate limiting and respectful scraping
        - Error handling and retry logic
        - Content validation for air quality data
        - Metadata extraction for data freshness

        Args:
            url: URL to scrape
            timeout: Request timeout in seconds

        Returns:
            Dict with scraped data and metadata, or None if failed
        """
        try:
            import random

            import requests
            from bs4 import BeautifulSoup

            # Enhanced user agents that mimic real browsers better
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ]

            # More realistic headers
            headers = {
                'User-Agent': random.choice(user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }

            # Rate limiting - respect website limits (increased delay)
            time.sleep(2)  # 2 second delay between requests

            # Add referer for some sites
            if 'nih.gov' in url or 'nature.com' in url or 'sciencedirect.com' in url:
                headers['Referer'] = 'https://www.google.com/'

            response = requests.get(url, headers=headers, timeout=timeout, verify=True, allow_redirects=True)
            response.raise_for_status()

            # Handle encoding issues
            if response.encoding is None or response.encoding == 'ISO-8859-1':
                response.encoding = response.apparent_encoding or 'utf-8'

            # Create BeautifulSoup with error handling
            soup = BeautifulSoup(response.content.decode(response.encoding, errors='replace'), 'html.parser')

            # Extract real-time data patterns
            realtime_data = self._extract_realtime_aqi_data(soup, url)

            if realtime_data:
                return {
                    'url': url,
                    'data': realtime_data,
                    'scraped_at': time.time(),
                    'status': 'success',
                    'source_type': 'realtime_scrape'
                }

            # If no specific AQI data found, extract general page info
            title = soup.title.text.strip() if soup.title else "No title"
            return {
                'url': url,
                'data': {'location': title, 'type': 'general_page'},
                'scraped_at': time.time(),
                'status': 'success',
                'source_type': 'general_scrape'
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.debug(f"Access forbidden for {url}: {e}")
            elif e.response.status_code == 429:
                logger.debug(f"Rate limited for {url}: {e}")
            else:
                logger.debug(f"HTTP error for {url}: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"Request error for {url}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error scraping {url}: {e}")
            return None

    def _extract_realtime_aqi_data(self, soup, url: str) -> Optional[dict]:
        """
        Extract real-time AQI data from various website formats.

        Supports common patterns from:
        - WAQI/AQICN sites
        - Government monitoring sites
        - AirQo and similar platforms
        """
        try:
            data = {}

            # WAQI/AQICN pattern
            aqi_element = soup.find('div', class_='aqi-value') or soup.find('span', class_='aqi')
            if aqi_element:
                try:
                    data['aqi'] = float(aqi_element.get_text().strip())
                except ValueError:
                    pass

            # AirQo pattern
            airqo_data = soup.find('div', {'data-testid': 'air-quality-data'})
            if airqo_data:
                # Extract PM2.5, PM10, etc.
                pm25 = airqo_data.find('span', string='PM2.5')
                if pm25:
                    value_elem = pm25.find_next('span')
                    if value_elem:
                        try:
                            data['pm25'] = float(value_elem.get_text().strip())
                        except ValueError:
                            pass

            # Generic pattern for any numeric data in common classes
            for class_name in ['aqi', 'pm25', 'pm10', 'o3', 'no2', 'so2', 'co']:
                elements = soup.find_all(class_=class_name)
                for elem in elements:
                    text = elem.get_text().strip()
                    try:
                        # Try to extract numeric values
                        import re
                        numbers = re.findall(r'\d+\.?\d*', text)
                        if numbers:
                            data[class_name] = float(numbers[0])
                            break
                    except:
                        continue

            # Extract location/city name
            location_selectors = [
                ('h1', {}),
                ('div', {'class': 'location'}),
                ('span', {'class': 'city-name'}),
                ('title', {})
            ]

            for tag, attrs in location_selectors:
                elem = soup.find(tag, attrs)
                if elem:
                    title_text = elem.get_text().strip()
                    # Clean up common prefixes
                    for prefix in ['Air Pollution:', 'Air Quality in', 'AQI -']:
                        if title_text.startswith(prefix):
                            title_text = title_text[len(prefix):].strip()
                    if title_text and len(title_text) > 3:
                        data['location'] = title_text
                        break

            # Extract timestamp if available
            time_elements = soup.find_all(['time', 'span'], class_=lambda x: x and 'time' in x.lower())
            for elem in time_elements:
                datetime_attr = elem.get('datetime')
                if datetime_attr:
                    data['timestamp'] = datetime_attr
                    break

            return data if data else None

        except Exception as e:
            logger.debug(f"Error extracting AQI data from {url}: {e}")
            return None

    def search_with_realtime_data(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """
        Enhanced search that combines web search with real-time data scraping.

        For air quality queries, this method:
        1. Performs web search to find relevant sources
        2. Scrapes real-time data from trusted sources
        3. Combines search results with live data

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            Enhanced results with real-time data where available
        """
        # First, perform regular search
        search_results = self.search(query, max_results)

        # Check if this is an air quality related query
        is_aq_query = any(keyword in query.lower() for keyword in [
            'air quality', 'aqi', 'pollution', 'pm2.5', 'pm10', 'ozone'
        ])

        if not is_aq_query:
            return search_results

        # For air quality queries, try to get real-time data from select trusted sources only
        enhanced_results = []

        # Only scrape from highly reliable sources to avoid 403 errors
        reliable_scrape_sources = [
            'aqicn.org', 'waqi.info', 'iqair.com', 'openaq.org',
            'airnow.gov', 'epa.gov', 'eea.europa.eu'
        ]

        for result in search_results:
            enhanced_result = dict(result)  # Copy original result
            enhanced_result['data_freshness'] = 'search_only'  # Default

            # Only attempt scraping for highly reliable sources
            url = result.get('href', '')
            if url:
                domain = self._extract_domain(url)
                if domain in reliable_scrape_sources:
                    try:
                        realtime_data = self.scrape_realtime_data(url)
                        if realtime_data and realtime_data.get('data'):
                            enhanced_result['realtime_data'] = realtime_data['data']
                            enhanced_result['data_freshness'] = 'realtime'
                            logger.debug(f"✓ Added real-time data for {domain}")
                        else:
                            logger.debug(f"No real-time data found for {domain}")
                    except Exception as e:
                        logger.debug(f"Failed to scrape {domain}: {e}")
                        # Continue without real-time data - don't fail the entire search

            enhanced_results.append(enhanced_result)

        return enhanced_results

    def search_air_quality_info(self, location: str, max_results: int = 5) -> list[dict[str, Any]]:
        """
        Specialized search for air quality information about a specific location.
        Automatically constructs relevant queries and combines results.
        Includes targeted queries for African air quality sources when applicable.

        **ENHANCED:** Dynamically discovers new air quality data sources and providers.

        Args:
            location: City or region name
            max_results: Maximum results per query

        Returns:
            Combined list of relevant search results
        """
        # Base queries for all locations - EXPANDED for better discovery
        queries = [
            f"{location} air quality monitoring stations",
            f"{location} AQI real-time data",
            f"{location} pollution levels 2025 2026",
            f"{location} environmental agency air quality",
            f"WHO air quality {location}",
            f"{location} air quality sensors monitoring network",  # NEW: discover sensor networks
            f"{location} atmospheric pollution data",  # NEW: broader search
        ]

        # Add IQAir-specific queries for enhanced coverage
        iqair_queries = [
            f"{location} air quality IQAir",
            f"site:iqair.com {location}",
        ]
        queries.extend(iqair_queries)

        # African-specific queries for African locations
        african_countries = [
            "kenya",
            "uganda",
            "tanzania",
            "rwanda",
            "burundi",
            "ethiopia",
            "somalia",
            "djibouti",
            "eritrea",
            "sudan",
            "south sudan",
            "egypt",
            "libya",
            "tunisia",
            "algeria",
            "morocco",
            "western sahara",
            "mauritania",
            "mali",
            "niger",
            "chad",
            "senegal",
            "gambia",
            "guinea-bissau",
            "guinea",
            "sierra leone",
            "liberia",
            "cote d'ivoire",
            "burkina faso",
            "ghana",
            "togo",
            "benin",
            "nigeria",
            "cameroon",
            "central african republic",
            "gabon",
            "congo",
            "democratic republic of congo",
            "angola",
            "zambia",
            "malawi",
            "mozambique",
            "zimbabwe",
            "namibia",
            "botswana",
            "south africa",
            "lesotho",
            "eswatini",
            "madagascar",
            "comoros",
            "mauritius",
            "seychelles",
            "cape verde",
            "sao tome and principe",
            "equatorial guinea",
        ]

        location_lower = location.lower()
        is_african = any(country in location_lower for country in african_countries)

        if is_african:
            # Add African-specific sources
            african_queries = [
                f"{location} airqo air quality",
                f"{location} african clean air network",
                f"{location} nesrea air quality",  # Nigeria
                f"{location} nema air quality",  # Kenya/Uganda
                f"{location} epa air quality",  # Ghana
                f"{location} saaqis air quality",  # South Africa
                f"{location} clean air fund africa",
                f"site:airqo.net {location}",
                f"site:cleanairafrica.org {location}",
            ]
            queries.extend(african_queries)

        all_results = []
        seen_urls = set()

        for query in queries:
            try:
                results = self.search(query, max_results=2)

                # Deduplicate by URL
                for result in results:
                    url = result.get("href", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(result)

                if len(all_results) >= max_results:
                    break

            except Exception as e:
                logger.warning(f"Error in specialized search for '{query}': {e}")
                continue

        return all_results[:max_results]

    def search_environmental_news(self, topic: str, max_results: int = 5) -> list[dict[str, Any]]:
        """
        Search for recent environmental and air quality news.
        Includes targeted queries for African air quality sources when topic is Africa-related.

        **ENHANCED:** Discovers emerging air quality data providers and research.

        Args:
            topic: Topic or location to search news for
            max_results: Maximum number of results

        Returns:
            List of news articles and reports
        """
        # Base news queries - EXPANDED for better discovery
        queries = [
            f"{topic} air quality environment news 2025 2026",
            f"{topic} air pollution monitoring research latest",  # NEW: research focus
            f"{topic} AQI data provider sources",  # NEW: discover new providers
        ]

        # Check if topic is Africa-related
        topic_lower = topic.lower()
        africa_keywords = [
            "africa",
            "african",
            "kenya",
            "uganda",
            "nigeria",
            "ghana",
            "south africa",
            "egypt",
            "morocco",
        ]
        is_africa_related = any(keyword in topic_lower for keyword in africa_keywords)

        if is_africa_related:
            # Add Africa-specific news sources
            africa_queries = [
                f"{topic} airqo news",
                f"{topic} clean air africa news",
                f"{topic} african clean air network news",
                f"site:cleanairafrica.org {topic} news",
                f"site:airqo.net {topic} news",
                f"{topic} air quality africa policy research",
            ]
            queries.extend(africa_queries)

        all_results = []
        seen_urls = set()

        for query in queries:
            try:
                results = self.search(query, max_results=2)

                # Deduplicate by URL
                for result in results:
                    url = result.get("href", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(result)

                if len(all_results) >= max_results:
                    break

            except Exception as e:
                logger.warning(f"Error in environmental news search for '{query}': {e}")
                continue

        return all_results[:max_results]

    def discover_air_quality_sources(
        self, location: str, max_results: int = 8
    ) -> list[dict[str, str]]:
        """
        Dynamically discover new air quality data sources and providers for a location.

        This method helps the agent find emerging or lesser-known air quality monitoring
        networks, citizen science projects, and regional providers that may not be in
        the primary trusted sources list.

        **USE CASE:** When primary APIs return no data, this discovers alternative sources
        like IQAir, PurpleAir, local government portals, university research projects, etc.

        Args:
            location: City, region, or country name
            max_results: Maximum number of data sources to discover

        Returns:
            List of search results focusing on data providers and monitoring networks
        """
        logger.info(f"Discovering air quality data sources for: {location}")

        discovery_queries = [
            f"{location} air quality data API monitoring network",
            f"{location} real-time air pollution sensors",
            f"{location} government environmental monitoring",
            f"{location} citizen science air quality project",
            f"{location} university air quality research data",
            f"site:iqair.com {location}",  # IQAir specific
            f"site:purpleair.com {location}",  # PurpleAir specific
            f"{location} atmospheric research station",
        ]

        all_sources = []
        seen_domains = set()

        for query in discovery_queries:
            try:
                results = self.search(query, max_results=2)

                for result in results:
                    href = result.get("href", "")
                    domain = self._extract_domain(href)

                    # Deduplicate by domain and prioritize data-focused results
                    if domain and domain not in seen_domains:
                        # Check if result mentions data/monitoring keywords
                        text_content = f"{result.get('title', '')} {result.get('body', '')}".lower()
                        data_keywords = [
                            "data",
                            "monitoring",
                            "sensor",
                            "api",
                            "real-time",
                            "aqi",
                            "pollution",
                        ]

                        if any(keyword in text_content for keyword in data_keywords):
                            seen_domains.add(domain)
                            all_sources.append(result)

                            # Mark as newly discovered source
                            result["discovered_source"] = "true"
                            result["relevance"] = (
                                "high" if self._is_trusted_source(href) else "medium"
                            )

                if len(all_sources) >= max_results:
                    break

            except Exception as e:
                logger.warning(f"Error in source discovery for '{query}': {e}")
                continue

        logger.info(
            f"Discovered {len(all_sources)} potential air quality data sources for {location}"
        )
        return all_sources[:max_results]
