from langchain_core.tools import tool
from tavily import TavilyClient
from dotenv import load_dotenv
import os

load_dotenv()

@tool
def listing_search(query: str) -> str:
    """Search for rental listings and market data. Use this to find comparable rentals near a specific address."""
    try:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        results = client.search(query, max_results=7)
        output = []
        for r in results["results"]:
            output.append(f"Source: {r['url']}\n{r['content']}")
        return "\n\n---\n\n".join(output)
    except Exception as e:
        return f"Search failed: {str(e)}"