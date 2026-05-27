"""
Slickdeals RSS fetcher.

Slickdeals exposes public RSS feeds. We pull the front-page feed (community-vetted
deals) and the "popular" feed. No auth, no API key needed.

Feeds:
    https://slickdeals.net/newsearch.php?mode=frontpage&rss=1     (front page)
    https://slickdeals.net/newsearch.php?mode=popdeals&rss=1      (popular)

Robots.txt allows these feeds. Respect rate limits - max 1 fetch per minute
per feed is more than enough (community posts deals throughout the day).
"""

import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

FEEDS = {
    "frontpage": "https://slickdeals.net/newsearch.php?mode=frontpage&rss=1",
    "popular": "https://slickdeals.net/newsearch.php?mode=popdeals&rss=1",
}


@dataclass
class Deal:
    source: str
    feed: str
    title: str
    deal_price: Optional[float]
    list_price: Optional[float]
    discount_pct: Optional[float]
    retailer: Optional[str]
    url: str
    description: str
    posted_at: Optional[str]

    def to_dict(self) -> dict:
        return self.__dict__.copy()


PRICE_RE = re.compile(r"\$([0-9]+(?:\.[0-9]{1,2})?)")
RETAILER_RE = re.compile(
    r"\b(Walmart|Target|Amazon|Best ?Buy|Kohl'?s|Costco|Sam'?s Club|"
    r"Home ?Depot|Lowe'?s|Macy'?s|Nordstrom|TJ ?Maxx|Marshalls|HomeGoods|"
    r"Ross|Big ?Lots|CVS|Walgreens|Dollar ?Tree|Dollar ?General|"
    r"Aliexpress|Temu|eBay|Newegg)\b",
    re.IGNORECASE,
)


def _http_get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def _extract_prices(text: str) -> tuple:
    prices = [float(m) for m in PRICE_RE.findall(text)]
    if not prices:
        return None, None
    if len(prices) == 1:
        return prices[0], None
    deal_price = min(prices)
    list_price = max(prices)
    if list_price <= deal_price:
        return deal_price, None
    return deal_price, list_price


def _extract_retailer(text: str) -> Optional[str]:
    m = RETAILER_RE.search(text)
    return m.group(1).strip() if m else None


def parse_rss(xml_bytes: bytes, feed_name: str) -> List[Deal]:
    deals = []
    root = ET.fromstring(xml_bytes)
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        desc = (item.findtext("description") or "").strip()
        url = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate")

        combined = f"{title} {desc}"
        deal_price, list_price = _extract_prices(combined)
        discount_pct = None
        if deal_price and list_price and list_price > 0:
            discount_pct = (list_price - deal_price) / list_price * 100

        deals.append(Deal(
            source="slickdeals",
            feed=feed_name,
            title=title,
            deal_price=deal_price,
            list_price=list_price,
            discount_pct=discount_pct,
            retailer=_extract_retailer(combined),
            url=url,
            description=desc[:500],
            posted_at=pub,
        ))
    return deals


def fetch(feed_name: str = "frontpage") -> List[Deal]:
    if feed_name not in FEEDS:
        raise ValueError(f"Unknown feed: {feed_name}. Use: {list(FEEDS.keys())}")
    try:
        xml_bytes = _http_get(FEEDS[feed_name])
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Slickdeals returned HTTP {e.code} - try again later")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach Slickdeals: {e.reason}")
    return parse_rss(xml_bytes, feed_name)


def fetch_all() -> List[Deal]:
    all_deals = []
    for name in FEEDS:
        try:
            all_deals.extend(fetch(name))
        except RuntimeError as e:
            print(f"  [warn] {name} feed failed: {e}")
    seen = set()
    deduped = []
    for d in all_deals:
        if d.url in seen:
            continue
        seen.add(d.url)
        deduped.append(d)
    return deduped


if __name__ == "__main__":
    print("Fetching Slickdeals frontpage feed...")
    deals = fetch("frontpage")
    print(f"Got {len(deals)} deals\n")
    for d in deals[:5]:
        print(f"  [{d.retailer or '?'}] {d.title[:80]}")
        print(f"    deal=${d.deal_price} list=${d.list_price} disc={d.discount_pct}")
        print(f"    {d.url}\n")
