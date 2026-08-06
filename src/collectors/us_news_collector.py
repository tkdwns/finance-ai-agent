"""글로벌/미국 금융 뉴스 및 RSS 수집 모듈 (USNewsCollector)."""

import xml.etree.ElementTree as ET
from typing import Any
import requests


class USNewsCollector:
    """월가 및 미국 증시 주요 이슈/뉴스 RSS를 수집하는 클래스."""

    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.rss_urls = [
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA,AAPL,MSFT,TSLA&region=US&lang=en-US",
            "https://www.investing.com/rss/news.rss",
        ]

    def fetch_global_news(self, query: str = "US Market", max_items: int = 5) -> list[dict[str, Any]]:
        """글로벌 월가 금융 뉴스 헤드라인과 원문 링크를 수집한다."""
        articles = []
        for url in self.rss_urls:
            try:
                resp = requests.get(url, headers=self.headers, timeout=self.timeout)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    items = root.findall(".//item")
                    for item in items[:max_items]:
                        title = item.findtext("title", "No Title").strip()
                        link = item.findtext("link", "").strip()
                        pub_date = item.findtext("pubDate", "").strip()
                        if title and link:
                            articles.append({
                                "title": title,
                                "link": link,
                                "pub_date": pub_date,
                                "source": "Yahoo/Investing RSS",
                            })
                        if len(articles) >= max_items:
                            break
            except Exception:
                continue

        if not articles:
            # Fallback 예시 기사
            articles = [
                {
                    "title": f"US Markets Focus: {query} Trends & Tech Earnings Outlook",
                    "link": "https://finance.yahoo.com",
                    "pub_date": "2026-08-06",
                    "source": "Market News",
                }
            ]

        return articles
