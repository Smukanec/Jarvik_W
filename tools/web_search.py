try:
    from duckduckgo_search import DDGS, DuckDuckGoSearchException
except ImportError:  # older versions don't expose DuckDuckGoSearchException
    from duckduckgo_search import DDGS  # type: ignore
    DuckDuckGoSearchException = Exception  # type: ignore
import requests
from bs4 import BeautifulSoup


def search_and_scrape(query: str, max_results: int = 1) -> str:
    """Return the first search result text for *query*.

    Any network failures during search are swallowed and an empty result is
    returned. This prevents the caller from crashing when DuckDuckGo blocks
    the request (for example, due to rate limiting).
    """
    with DDGS() as ddgs:
        try:
            results = list(ddgs.text(query, max_results=max_results))
        except DuckDuckGoSearchException:
            results = []
    if not results:
        return "\u26a0\ufe0f \u017d\u00e1dn\u00e9 v\u00fdsledky nenalezeny."

    url = results[0]["href"]
    try:
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        return f"🔗 {url}\n\n{text[:2000]}…"
    except Exception as e:  # pragma: no cover - network dependent
        return f"❌ Chyba p\u0159i na\u010d\u00edt\u00e1n\u00ed: {e}"
