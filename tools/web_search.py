from duckduckgo_search import ddg
import requests
from bs4 import BeautifulSoup


def search_and_scrape(query: str, max_results: int = 1) -> str:
    """Return the first search result text for *query*."""
    results = ddg(query, max_results=max_results)
    if not results:
        return "\u26a0\ufe0f \u017d\u00e1dn\u00e9 v\u00fdsledky nenalezeny."

    url = results[0]["href"]
    try:
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        return f"\ud83d\udd17 {url}\n\n{text[:2000]}\u2026"
    except Exception as e:  # pragma: no cover - network dependent
        return f"\u274c Chyba p\u0159i na\u010d\u00edt\u00e1n\u00ed: {e}"
