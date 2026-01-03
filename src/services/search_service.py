import logging

try:
    from ddgs import DDGS
except ImportError:
    # Fallback if ddgs not installed yet
    from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


class SearchService:
    """
    Service for performing web searches using DuckDuckGo.
    Enhanced for air quality and environmental information searches.
    """

    # Trusted air quality and environmental sources
    TRUSTED_SOURCES = [
        # Core air quality platforms
        "airqo.net",
        "airqo.africa",
        "airqo.org",
        "cleanairafrica.org",
        "aero-glyphs.vercel.app",
        "aqicn.org",
        "openaq.org",
        "iqair.com",
        "plumelabs.com",
        "waqi.info",
        "open-meteo.com",
        "carbonintensity.org.uk",
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
        # Research and academic
        "nature.com",
        "sciencedirect.com",
        "nih.gov",
        "cdc.gov",
        "up.ac.za",
        "icraq.org",
        # Satellite and remote sensing
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

    def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """
        Performs a web search using DuckDuckGo.
        Returns a list of search results with 'title', 'href', and 'body' fields.

        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 5)

        Returns:
            List of search result dictionaries with title, href, and body
        """
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                logger.warning(f"No search results found for query: {query}")
                return [
                    {
                        "title": "No results",
                        "body": "No search results found for this query.",
                        "href": "",
                    }
                ]

            # Prioritize trusted sources
            results = self._prioritize_trusted_sources(results)

            logger.info(f"Found {len(results)} search results for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Error performing search for '{query}': {e}")
            return [
                {
                    "title": "Search Error",
                    "body": f"Failed to perform search: {str(e)}",
                    "href": "",
                }
            ]

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

        Args:
            location: City or region name
            max_results: Maximum results per query

        Returns:
            Combined list of relevant search results
        """
        # Base queries for all locations
        queries = [
            f"{location} air quality monitoring stations",
            f"{location} pollution levels 2025",
            f"{location} environmental agency air quality",
            f"WHO air quality {location}",
        ]

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

        Args:
            topic: Topic or location to search news for
            max_results: Maximum number of results

        Returns:
            List of news articles and reports
        """
        # Base news queries
        queries = [f"{topic} air quality environment news 2025"]

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
