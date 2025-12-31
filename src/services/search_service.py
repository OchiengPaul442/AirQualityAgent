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
        "who.int",
        "epa.gov",
        "airquality.gov",
        "aqicn.org",
        "iqair.com",
        "unep.org",
        "worldbank.org",
        "nature.com",
        "sciencedirect.com",
        "nih.gov",
        "cdc.gov",
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
        
        Args:
            location: City or region name
            max_results: Maximum results per query
            
        Returns:
            Combined list of relevant search results
        """
        queries = [
            f"{location} air quality monitoring stations",
            f"{location} pollution levels 2025",
            f"{location} environmental agency air quality",
            f"WHO air quality {location}",
        ]
        
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
        
        Args:
            topic: Topic or location to search news for
            max_results: Maximum number of results
            
        Returns:
            List of news articles and reports
        """
        query = f"{topic} air quality environment news 2025"
        return self.search(query, max_results=max_results)
