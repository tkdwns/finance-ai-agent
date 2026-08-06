"""
DB 테이블 정의.

설계 원칙 (docs/DB_SCHEMA.md 에 상세 설명):
1. 자산군(주식/채권/부동산/암호화폐)별로 테이블을 분리한다.
2. 각 자산군 내에서도 콘텐츠 유형(뉴스/공시/지표/거래/정책/공지)별로 테이블을 나눈다.
3. 법령 개정(자본시장법/은행법/금융소비자보호법)은 특정 자산군에 속하지 않고
   여러 자산군에 걸쳐 있을 수 있어 별도 테이블 + 다대다 연결 테이블로 관리한다.
4. 키워드 추출 결과와 생성된 보고서는 자산군 x 기간 축으로 별도 테이블에 저장한다.
"""

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AssetClass(str, PyEnum):
    STOCK = "stock"
    BOND = "bond"
    REAL_ESTATE = "real_estate"
    CRYPTO = "crypto"


class PeriodType(str, PyEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


# ---------------------------------------------------------------------------
# 공통 Mixin
# 뉴스/공시/정책/공지처럼 "문서형(제목+요약+링크)" 데이터가 공유하는 필드.
# 각 서브클래스는 이 필드들을 상속받아 자신만의 테이블로 생성된다.
# ---------------------------------------------------------------------------
class DocumentMixin:
    id = Column(Integer, primary_key=True)
    source = Column(String(100), nullable=False)          # 예: "DART", "한국경제", "업비트"
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False, unique=True)
    summary = Column(Text, default="")                     # 원문 전체 저장 금지, 요약만 저장 (저작권 원칙)
    published_at = Column(DateTime, nullable=False)
    collected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# 1. 주식 (Stock) — 1순위 MVP 대상
# ---------------------------------------------------------------------------
class StockNews(DocumentMixin, Base):
    __tablename__ = "stock_news"
    related_ticker = Column(String(20), nullable=True)      # 관련 종목코드 (있으면)


class StockDisclosure(DocumentMixin, Base):
    """DART 공시 정보."""

    __tablename__ = "stock_disclosures"
    corp_name = Column(String(200), nullable=False)          # 기업명
    corp_code = Column(String(20), nullable=False)            # DART 고유번호
    rcept_no = Column(String(20), nullable=False, unique=True)  # 공시 접수번호
    report_name = Column(String(300), nullable=False)          # 보고서명 (예: "분기보고서")


# ---------------------------------------------------------------------------
# 2. 채권 (Bond)
# ---------------------------------------------------------------------------
class BondNews(DocumentMixin, Base):
    __tablename__ = "bond_news"


class BondIndicator(Base):
    """한국은행 ECOS/FRED 등에서 가져오는 수치형 지표 (금리, 지수 등).
    뉴스와 달리 제목/링크가 없는 시계열 데이터라 별도 스키마를 사용한다.
    asset_class는 기존 행에는 없던 컬럼이라 nullable(레거시 행은 NULL -> "bond"로 취급)."""

    __tablename__ = "bond_indicators"
    id = Column(Integer, primary_key=True)
    indicator_code = Column(String(50), nullable=False)       # ECOS 통계표 코드 / FRED series_id
    indicator_name = Column(String(200), nullable=False)       # 예: "국고채 3년물 금리", "나스닥종합지수"
    asset_class = Column(Enum(AssetClass), nullable=True)      # "bond" | "stock" 등, 리포트 필터링용
    date = Column(DateTime, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(20), default="%")
    source = Column(String(100), default="ECOS")
    collected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("indicator_code", "date", name="uq_bond_indicator_date"),
    )


# ---------------------------------------------------------------------------
# 3. 부동산 (Real Estate)
# ---------------------------------------------------------------------------
class RealEstateNews(DocumentMixin, Base):
    __tablename__ = "real_estate_news"


class RealEstateTransaction(Base):
    """국토교통부 실거래가 공개시스템 데이터. 뉴스와 별도의 정형 데이터 스키마."""

    __tablename__ = "real_estate_transactions"
    id = Column(Integer, primary_key=True)
    region = Column(String(100), nullable=False)               # 시군구
    complex_name = Column(String(200), nullable=True)            # 단지명
    transaction_price = Column(Float, nullable=False)              # 만원 단위
    area_m2 = Column(Float, nullable=True)
    floor = Column(Integer, nullable=True)
    transaction_date = Column(DateTime, nullable=False)
    source = Column(String(100), default="MOLIT")
    collected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RealEstatePolicy(DocumentMixin, Base):
    """대출규제, 세제, 공급대책 등 부동산 관련 정책 발표."""

    __tablename__ = "real_estate_policies"
    policy_type = Column(String(50), nullable=True)              # 예: "대출규제", "세제", "공급대책"


# ---------------------------------------------------------------------------
# 4. 암호화폐 (Crypto)
# ---------------------------------------------------------------------------
class CryptoNews(DocumentMixin, Base):
    __tablename__ = "crypto_news"


class CryptoNotice(DocumentMixin, Base):
    """거래소 공지(상장/유의/거래정지 등) 및 금융당국 발표."""

    __tablename__ = "crypto_notices"
    exchange_name = Column(String(100), nullable=True)            # 예: "업비트", "빗썸" (당국 발표면 null)
    notice_type = Column(String(50), nullable=True)               # 예: "상장", "유의종목", "거래정지"


# ---------------------------------------------------------------------------
# 5. 법·규제 (자본시장법 / 은행법 / 금융소비자보호법 개정 동향)
#    특정 자산군에 종속되지 않고 여러 자산군에 걸칠 수 있어 다대다 연결 테이블 사용
# ---------------------------------------------------------------------------
law_amendment_asset_class = Table(
    "law_amendment_asset_class",
    Base.metadata,
    Column("law_amendment_id", Integer, ForeignKey("law_amendments.id"), primary_key=True),
    Column("asset_class", Enum(AssetClass), primary_key=True),
)


class LawAmendment(DocumentMixin, Base):
    __tablename__ = "law_amendments"
    law_name = Column(String(100), nullable=False)                 # 자본시장법/은행법/금융소비자보호법 중 하나
    amendment_date = Column(DateTime, nullable=True)                 # 시행일/개정일
    amendment_reason_summary = Column(Text, default="")               # 개정 이유 요약 (조문 전문 저장 금지)


# ---------------------------------------------------------------------------
# 6. 키워드 추출 결과 (자산군 x 기간 축)
# ---------------------------------------------------------------------------
class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(Integer, primary_key=True)
    asset_class = Column(Enum(AssetClass), nullable=False)
    period_type = Column(Enum(PeriodType), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    keyword = Column(String(100), nullable=False)
    score = Column(Float, default=0.0)                               # TF-IDF/빈도 등 중요도 점수
    explanation = Column(Text, default="")                            # LLM이 생성한 트렌드 설명 (있으면)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint(
            "asset_class", "period_type", "period_start", "keyword", name="uq_keyword_period"
        ),
    )


# ---------------------------------------------------------------------------
# 7. 생성된 보고서
# ---------------------------------------------------------------------------
class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    period_type = Column(Enum(PeriodType), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    asset_class = Column(Enum(AssetClass), nullable=True)              # null이면 전체 자산군 통합 보고서
    content_markdown = Column(Text, nullable=False)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
