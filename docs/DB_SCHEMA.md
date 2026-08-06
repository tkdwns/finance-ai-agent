# DB 스키마 설계

## 설계 원칙

1. **자산군별 테이블 분리**: 주식(stock) / 채권(bond) / 부동산(real_estate) / 암호화폐(crypto)를
   각각 독립된 테이블 그룹으로 관리한다.
2. **자산군 내 콘텐츠 유형별 분리**: 같은 자산군이라도 뉴스, 공시, 정책, 지표, 거래 등
   콘텐츠 유형에 따라 스키마가 다르므로 테이블을 나눈다.
3. **문서형 데이터는 공통 Mixin 사용**: 뉴스/공시/정책/공지처럼 "제목+요약+링크" 구조를
   공유하는 테이블은 `DocumentMixin`을 상속받아 필드 중복 정의를 없앤다.
4. **수치형 데이터는 별도 스키마**: 채권 지표(금리 등)와 부동산 실거래가처럼 제목·링크가
   없는 정형 통계 데이터는 문서형과 다른 전용 스키마를 사용한다.
5. **법·규제는 자산군에 종속되지 않음**: 자본시장법/은행법/금융소비자보호법 개정은
   여러 자산군에 걸쳐 영향을 줄 수 있으므로 별도 테이블 + 다대다 연결 테이블로 관리한다.
6. **원문 전체 저장 금지**: 모든 문서형 테이블의 `summary` 필드는 요약만 저장하고,
   원문 전문은 저장하지 않는다 (저작권 원칙).

## 테이블 목록

### 공통 Mixin — `DocumentMixin`
다음 테이블들이 공통으로 상속받는 필드:

| 필드명 | 타입 | 설명 |
|---|---|---|
| id | Integer (PK) | 기본키 |
| source | String(100) | 출처 (예: "DART", "한국경제", "업비트") |
| title | String(500) | 제목 |
| url | String(1000), unique | 원문 링크 |
| summary | Text | 요약 (원문 전체 금지) |
| published_at | DateTime | 발행/공시/시행 일시 |
| collected_at | DateTime | 수집 시각 (자동 기록) |

---

### 1. 주식 (Stock) — 1순위 MVP 대상

**`stock_news`** (DocumentMixin 상속)
| 추가 필드 | 타입 | 설명 |
|---|---|---|
| related_ticker | String(20), nullable | 관련 종목코드 (있으면) |

**`stock_disclosures`** — DART 공시 (DocumentMixin 상속)
| 추가 필드 | 타입 | 설명 |
|---|---|---|
| corp_name | String(200) | 기업명 |
| corp_code | String(20) | DART 고유번호 |
| rcept_no | String(20), unique | 공시 접수번호 |
| report_name | String(300) | 보고서명 (예: "분기보고서") |

---

### 2. 채권 (Bond)

**`bond_news`** (DocumentMixin 상속, 추가 필드 없음)

**`bond_indicators`** — ECOS 등 수치형 지표 (독립 스키마)
| 필드 | 타입 | 설명 |
|---|---|---|
| id | Integer (PK) | 기본키 |
| indicator_code | String(50) | ECOS 통계표 코드 |
| indicator_name | String(200) | 예: "국고채 3년물 금리" |
| date | DateTime | 지표 기준일 |
| value | Float | 값 |
| unit | String(20) | 단위 (기본 "%") |
| source | String(100) | 기본 "ECOS" |
| collected_at | DateTime | 수집 시각 |

Unique 제약: `(indicator_code, date)` — 같은 지표의 같은 날짜 중복 저장 방지

---

### 3. 부동산 (Real Estate)

**`real_estate_news`** (DocumentMixin 상속, 추가 필드 없음)

**`real_estate_transactions`** — 국토부 실거래가 (독립 스키마)
| 필드 | 타입 | 설명 |
|---|---|---|
| id | Integer (PK) | 기본키 |
| region | String(100) | 시군구 |
| complex_name | String(200), nullable | 단지명 |
| transaction_price | Float | 거래가 (만원 단위) |
| area_m2 | Float, nullable | 전용면적(㎡) |
| floor | Integer, nullable | 층 |
| transaction_date | DateTime | 거래일 |
| source | String(100) | 기본 "MOLIT" |
| collected_at | DateTime | 수집 시각 |

**`real_estate_policies`** — 대출규제/세제/공급대책 등 정책 (DocumentMixin 상속)
| 추가 필드 | 타입 | 설명 |
|---|---|---|
| policy_type | String(50), nullable | 예: "대출규제", "세제", "공급대책" |

---

### 4. 암호화폐 (Crypto)

**`crypto_news`** (DocumentMixin 상속, 추가 필드 없음)

**`crypto_notices`** — 거래소 공지 및 당국 발표 (DocumentMixin 상속)
| 추가 필드 | 타입 | 설명 |
|---|---|---|
| exchange_name | String(100), nullable | 예: "업비트", "빗썸" (당국 발표면 null) |
| notice_type | String(50), nullable | 예: "상장", "유의종목", "거래정지" |

---

### 5. 법·규제 — `law_amendments` (DocumentMixin 상속)

자본시장법 / 은행법 / 금융소비자보호법의 개정 동향만 다룬다 (판례·소송 제외).

| 추가 필드 | 타입 | 설명 |
|---|---|---|
| law_name | String(100) | 3개 법령 중 하나 |
| amendment_date | DateTime, nullable | 시행일/개정일 |
| amendment_reason_summary | Text | 개정 이유 요약 (조문 전문 저장 금지) |

**`law_amendment_asset_class`** — 다대다 연결 테이블
법령 개정 하나가 여러 자산군에 영향을 줄 수 있으므로 (예: 자본시장법 개정이 주식·채권 모두에 영향),
연결 테이블로 관리한다.

| 필드 | 타입 | 설명 |
|---|---|---|
| law_amendment_id | Integer (FK → law_amendments.id) | |
| asset_class | Enum(stock/bond/real_estate/crypto) | |

---

### 6. 키워드 추출 결과 — `keywords`

자산군 x 기간 축으로 저장. 일별/주별/월별/연별 보고서 생성 시 이 테이블을 조회한다.

| 필드 | 타입 | 설명 |
|---|---|---|
| id | Integer (PK) | 기본키 |
| asset_class | Enum | stock/bond/real_estate/crypto |
| period_type | Enum | daily/weekly/monthly/yearly |
| period_start | DateTime | 기간 시작일 |
| period_end | DateTime | 기간 종료일 |
| keyword | String(100) | 추출된 키워드 |
| score | Float | TF-IDF/빈도 등 중요도 점수 |
| created_at | DateTime | 생성 시각 |

Unique 제약: `(asset_class, period_type, period_start, keyword)`

---

### 7. 생성된 보고서 — `reports`

| 필드 | 타입 | 설명 |
|---|---|---|
| id | Integer (PK) | 기본키 |
| period_type | Enum | daily/weekly/monthly/yearly |
| period_start | DateTime | 기간 시작일 |
| period_end | DateTime | 기간 종료일 |
| asset_class | Enum, nullable | null이면 전체 자산군 통합 보고서 |
| content_markdown | Text | 생성된 보고서 본문 (Markdown) |
| generated_at | DateTime | 생성 시각 |

---

## 설계 시 고려한 트레이드오프

- **장점**: 자산군별로 테이블이 분리되어 있어, 특정 자산군만 조회/집계할 때 쿼리가 단순하고
  각 자산군의 고유한 필드(종목코드, 접수번호, 실거래가 등)를 자유롭게 추가할 수 있다.
- **단점**: 테이블 수가 많아진다 (현재 12개). "모든 자산군의 오늘자 뉴스"처럼 자산군을
  가로지르는 조회가 필요할 때는 여러 테이블을 UNION 해야 한다.
- 이 트레이드오프는 초기 단계에서는 자산군별 우선순위(주식 1순위, 나머지 2순위)에 따라
  점진적으로 확장하기 좋다는 장점이 더 크다고 판단해 채택했다. 추후 자산군 간 통합 조회가
  잦아지면 뷰(View) 또는 자산군 통합 조회용 헬퍼 함수를 추가하는 방식으로 보완할 수 있다.

## 검증 완료

`src/storage/models.py`의 모든 테이블은 SQLite in-memory DB 기준으로
`Base.metadata.create_all()` 실행 시 오류 없이 생성됨을 확인했다 (12개 테이블).
