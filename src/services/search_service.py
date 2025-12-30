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
    """

    def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """
        Performs a web search using DuckDuckGo.
        Returns a list of search results with 'title', 'href', and 'body' fields.
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
