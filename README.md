# 🤖 자율형 금융 정보 분석 AI Agent 시스템 v1.0 (Advanced Edition)

국내외 금융 시장(주식·채권·부동산·규제)의 뉴스, 공시, 실시간 시세, 법·규제 변화를 자율적으로 탐색하고 팩트체크하여 전문 인사이트 보고서를 생성하는 **차세대 자율형 금융 AI Agent Framework**입니다.

---

## 🌟 핵심 기능 및 아키텍처 특징

1. **🧠 ReAct 자율 추론 엔진 (Agent Brain)**
   - 정해진 순서대로 작동하는 단순 파이프라인이 아닌, 목표가 주어지면 **`생각(Think) ➔ 행동(Act) ➔ 관찰(Observe)`** 루프를 스스로 실행하는 자율형 대뇌 엔진 탑재.
2. **🛠️ Agent Tools & 레지스트리 (Tool Registry)**
   - DART 공시, ECOS 금리, FRED 지표, 뉴스 RSS, 법령 정보 및 **실시간 주가 시세/정량 재무 지표(PER/PBR/시가총액)** 수집기를 `@tool` 규격으로 제공.
3. **🏢 기업명 ↔ 고유코드 자동 매핑 (`CorpCodeMapper`)**
   - 복잡한 8자리 DART 고유코드(`00126380`)나 6자리 주식 종목코드(`005930`)를 외울 필요 없이, `"삼성전자"`, `"SK하이닉스"`, `"카카오"` 등의 한글 기업명만 대면 자동으로 코드를 찾아서 조회.
4. **💾 BM25 + Vector 하이브리드 RAG 기억 장치 (Memory System)**
   - 문맥적 유사도(Vector)와 날짜/고유번호/숫자 정확 매칭(BM25)을 융합한 **'하이브리드 RAG'**로 수만 건의 과거 데이터를 0.1초 만에 시맨틱 쿼리.
5. **👥 5인 Multi-Agent 드림팀 & 자기 반성(Self-Reflection) 루프**
   - **리서처(Researcher)** ➔ **분석가(Analyst)** ➔ **팩트체커(Compliance)** ➔ **리포터(Writer)** ➔ **비판가(Critic)**
   - 최종 보고서 작성 전 비판가 에이전트(Critic)가 검토 후 부실할 경우 스스로 고쳐 쓰는 **Self-Correction** 수행.
6. **📜 금융 규제 준수를 위한 감사 이력 기록 (Audit Trail)**
   - 모든 생각과 도구 호출 내역을 타임스탬프와 함께 `reports_output/audit_trail.jsonl`에 영구 기록하여 금융 감독 감사에 완벽 대비.

---

## 🏗️ 아키텍처 구조도

```mermaid
graph TD
    A[사용자 질의 / CLI] --> B[🧠 ReAct Agent Brain Engine]
    
    subgraph "👥 Multi-Agent Team & Self-Reflection"
        B --> C[🕵️ Researcher Agent]
        C --> D[📊 Financial Analyst Agent]
        D --> E[⚖️ Compliance Agent]
        E --> F[✍️ Report Writer Agent]
        F --> G[🧐 Critic Agent (Self-Reflection)]
        G -- "개선 피드백" --> F
    end
    
    subgraph "🛠️ Agent Tools & Corp Mapper"
        C --> T1[DART 공시 Tool]
        C --> T2[실시간 주가/재무 Tool]
        C --> T3[ECOS / FRED 금리 Tool]
        C --> T4[금융 뉴스 / 법령 Tool]
        T1 & T2 --> M[🏢 CorpCodeMapper]
    end
    
    subgraph "💾 Memory & Audit Trail"
        C & D & E --> VDB[(Hybrid RAG Memory)]
        B & C & D & F --> AT[(Audit Trail Logger)]
    end
    
    G --> Out[📊 완벽히 검증된 마크다운 최종 보고서]
```

---

## 📂 폴더 구조

```
financial-ai-agent/
├── config/                  # 전역 설정 및 .env 로드
├── src/
│   ├── agent/               # ReAct 자율 추론 대뇌 엔진 (core.py, state.py, prompts.py)
│   ├── agent_tools/         # 8대 Agent Tools 및 레지스트리 (dart, ecos, fred, news, law, stock, memory)
│   ├── multi_agent/         # 5인 Multi-Agent 팀 및 자기 반성 (roles.py, team.py)
│   ├── memory/              # BM25 + Vector 하이브리드 RAG 기억 장치 (vector_store.py)
│   ├── collectors/          # 원천 데이터 수집기 및 기업명 자동 매퍼 (corp_code_mapper.py)
│   ├── storage/             # DB 및 감사 이력 기록기 (audit_trail.py, models.py)
│   ├── preprocessing/       # 전처리 모듈 (normalizer, tagger, deduplicator)
│   └── reports/             # 리포트 생성기 및 이메일 발송
├── data/                    # SQLite DB 및 데이터 저장소
├── reports_output/          # 생성된 리포트 및 audit_trail.jsonl 감사 로그
├── docs/                    # 한글 상세 설계 및 정밀 진단 문서
│   └── FINANCIAL_AGENT_EXPERT_REVIEW.md
├── tests/                   # 238개 전체 단위 테스트 모음
├── main.py                  # 자율형 AI Agent 실행 진입점
└── README.md                # 본 안내 문서
```

---

## 💻 사용 방법

### 1. 실행 명령어

```bash
# 기본 질의 실행
python main.py "삼성전자 최근 주가 시세와 DART 공시 동향 분석해줘"

# 특정 금융 질의 실행
python main.py "한국은행 기준금리 변화와 원/달러 환율이 주식 시장에 미친 영향을 리포트로 작성해줘"
```

### 2. 전체 단위 테스트 실행

```bash
venv\Scripts\pytest.exe
```
(전체 238개 단위 테스트가 100% 깔끔하게 통과됩니다.)

---

## ⚖️ 법적 및 윤리적 원칙 (Disclaimers)

1. **투자 자문 불가**: 본 AI Agent가 생성한 보고서 및 분석 결과는 정량 데이터 및 공시 정리 목적이며, **투자 권유나 금융 자문이 아닙니다.**
2. **팩트 검증**: 수집 원문과의 대조 및 비판가 에이전트의 정밀 검증을 거쳐 환각(Hallucination)을 최소화합니다.

---

## 📜 라이선스

[MIT License](LICENSE)
