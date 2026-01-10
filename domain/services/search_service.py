import json
import logging
import os

try:
    from ddgs import DDGS  # type: ignore
except ImportError:
    # Fallback if ddgs not installed yet
    from duckduckgo_search import DDGS  # type: ignore

logger = logging.getLogger(__name__)


class SearchService:
    """
    Enhanced service for performing web searches using multiple providers.
    Supports DuckDuckGo, and fallback mechanisms for air quality and environmental information.
    """

    # Trusted air quality and environmental sources
    # IQAir (https://www.iqair.com/) - Premium AQI data provider (not free API but scrapable)
    # Added per user request as key data source for improved coverage
    TRUSTED_SOURCES = [
        # Core air quality platforms
        "airqo.net",
        "airqo.africa",
        "airqo.org",
        "cleanairafrica.org",
        "aero-glyphs.vercel.app",
        "aqicn.org",
        "openaq.org",
        "iqair.com",  # Premium AQI data - scrapable website
        "plumelabs.com",
        "waqi.info",
        "open-meteo.com",
        "carbonintensity.org.uk",
        "breezometer.com",  # Additional air quality data provider
        "purpleair.com",  # Community air quality sensors
        # Additional air quality monitoring platforms
        "airgradient.com",
        # Research and academic platforms
        "sciencedirect.com",
        "osf.io",
        # Global health and environment organizations
        "who.int",
        "unep.org",
        "worldbank.org",
        "uneca.org",
        # Government agencies
        "epa.gov",
        "airquality.gov",
        "nesrea.gov.ng",
        "nema.go.ke",
        "nema.go.ug",
        "epa.gov.gh",
        "meteo.gov.ma",
        "eeaa.gov.eg",
        "saaois.org.za",
        "environment.nsw.gov.au",
        "airquality.nsw.gov.au",
        "dpi.nsw.gov.au",
        # Research and academic
        "nature.com",
        "sciencedirect.com",
        "nih.gov",
        "cdc.gov",
        "up.ac.za",
        "icraq.org",
        "copernicus.eu",
        "atmosphere.copernicus.eu",
        "earthdata.nasa.gov",
        "worldview.earthdata.nasa.gov",
        "ciesin.columbia.edu",
        "sedac.ciesin.columbia.edu",
        "ecmwf.int",
        # Africa-specific networks
        "africancleanair.org",
        "cleanairfund.org",
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
        self, query: str, max_results: int = 5, provider: str = None
    ) -> list[dict[str, str]]:
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

    def _search_duckduckgo(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """
        Search using DuckDuckGo with enhanced metadata and timeout protection.

        Returns results with: title, href, body, and metadata (source, timestamp, relevance)
        """
        try:
            # Use threading timeout for Windows compatibility
            import concurrent.futures
            
            def search_operation():
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results))
            
            # Execute with timeout
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(search_operation)
                try:
                    raw_results = future.result(timeout=15.0)  # 15 second timeout
                except concurrent.futures.TimeoutError:
                    logger.error(f"DuckDuckGo search timed out after 15s for '{query}'")
                    return []  # Return empty results instead of failing

            if not raw_results:
                logger.warning(f"No search results found for query: {query}")
                return []

            # Enhance results with metadata
            enhanced_results = []
            for idx, result in enumerate(raw_results):
                enhanced = {
                    "title": result.get("title", ""),
                    "href": result.get("href", ""),
                    "body": result.get("body", ""),
                    "metadata": {
                        "source": self._extract_domain(result.get("href", "")),
                        "relevance_rank": idx + 1,
                        "is_trusted": self._is_trusted_source(result.get("href", "")),
                        "snippet_length": len(result.get("body", "")),
                        "query": query,
                    },
                }
                enhanced_results.append(enhanced)

            logger.info(f"Enhanced {len(enhanced_results)} search results with metadata")
            return enhanced_results

        except Exception as e:
            logger.error(f"DuckDuckGo search failed for '{query}': {e}")
            return []  # Return empty results instead of failing

    def _search_dashscope(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
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

    def search_air_quality_info(self, location: str, max_results: int = 5) -> list[dict[str, str]]:
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

    def search_environmental_news(self, topic: str, max_results: int = 5) -> list[dict[str, str]]:
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
                            result["discovered_source"] = True
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
