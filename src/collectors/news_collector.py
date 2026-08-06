"""
뉴스 수집기 (RSS 기반).

2단계 확장 대상. 언론사 RSS 피드에서 금융 관련 기사를 수집한다.
주식 뉴스든 채권 뉴스든 소스(RSS 피드) 자체는 자산군을 구분하지 않는다 — 기사 하나의
asset_class는 여기서 정하지 않고 비워둔 채 반환하며, src/preprocessing/tagger.py의
규칙 기반 키워드 매칭이 제목+요약을 보고 stock/bond/real_estate/crypto 중 하나로
분류한다 (분류 실패 시 "unknown").

주의:
- 기사 원문 전체를 저장하지 않는다. 제목 + 요약(RSS description) + 링크만 저장한다.
- 크롤링 대상 사이트의 robots.txt와 이용약관을 사전에 확인한다 (RSS 목록 선정은
  config.settings.news_rss_urls / .env의 NEWS_RSS_URLS를 통해 직접 채워 넣어야 한다).
"""

from datetime import datetime

import feedparser

from config.settings import settings
from src.collectors.base import BaseCollector, RawItem


class NewsCollector(BaseCollector):
    source_name = "news_rss"

    def __init__(self, rss_urls: list[str] | None = None):
        self.rss_urls = rss_urls if rss_urls is not None else settings.news_rss_urls

    def collect(self, start_date: datetime, end_date: datetime) -> list[RawItem]:
        """
        등록된 RSS 피드를 전부 조회해 기간 내 기사만 RawItem으로 반환한다.

        rss_urls가 비어 있으면(=아직 소스를 선정하지 않았으면) 빈 리스트를 반환한다.
        피드 하나가 파싱에 실패해도 나머지 피드는 계속 처리한다.
        """
        if not self.rss_urls:
            return []

        all_items: list[RawItem] = []
        for url in self.rss_urls:
            all_items.extend(self._collect_from_feed(url, start_date, end_date))
        return all_items

    def _collect_from_feed(self, url: str, start_date: datetime, end_date: datetime) -> list[RawItem]:
        parsed = feedparser.parse(url)

        # feedparser는 네트워크/파싱 오류 시에도 예외를 던지지 않고 bozo=1 플래그와
        # entries=[]를 반환하는 경우가 많다. 피드 하나가 죽어도 전체 수집이 멈추지
        # 않도록, 에러는 로그만 남기고 빈 리스트로 넘어간다.
        if getattr(parsed, "bozo", False) and not parsed.entries:
            print(f"      경고: RSS 피드 파싱 실패, 건너뜁니다 ({url}): {getattr(parsed, 'bozo_exception', '')}")
            return []

        feed_source = getattr(parsed.feed, "title", url) if hasattr(parsed, "feed") else url

        items: list[RawItem] = []
        for entry in parsed.entries:
            published_at = self._parse_published(entry)
            if published_at is None or not (start_date <= published_at <= end_date):
                continue

            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link:
                continue

            summary = entry.get("summary", "") or entry.get("description", "")

            items.append(
                RawItem(
                    source=feed_source,
                    asset_class="",  # tagger.py가 제목/요약 기반으로 채운다
                    title=title,
                    url=link,
                    published_at=published_at,
                    summary=summary,
                    raw_meta={"feed_url": url},
                )
            )
        return items

    @staticmethod
    def _parse_published(entry) -> datetime | None:
        time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if time_struct is None:
            return None
        try:
            return datetime(*time_struct[:6])
        except (TypeError, ValueError):
            return None
