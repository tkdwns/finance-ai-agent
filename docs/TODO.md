# 향후 처리할 작업 목록

우선순위 순서는 아니고, 발견 시점 순으로 기록. 처리되면 체크하고 날짜/커밋 남길 것.

## 미해결

(현재 없음 — 아래 "대기 중" 항목만 남음)

## 대기 중 (외부 요인)

- [ ] **MOLIT_API_KEY 발급 — 공공데이터포털 점검으로 보류**
      (2026-07-30 확인, 2026-08-01 재확인 — 여전히 로그인 불가)
      공공데이터포털(data.go.kr)이 2026-08-02까지 점검 중이라 로그인/회원가입/신규 API
      활용신청이 모두 불가능한 상태. 2026-08-01에 다시 로그인 시도했으나 아직 점검 중이라
      실패. 부동산(MOLIT) 실거래가 수집기(`collect_real_estate.py`)는 코드상 완성되어
      있으나, 실제 키 발급 후 로컬에서 라이브 테스트를 아직 못한 상태.
      점검 종료(2026-08-02 이후) 후 순서: https://www.data.go.kr 로그인 →
      "국토교통부_아파트 매매 실거래가 자료" 데이터셋 검색 → 활용신청(Open API) →
      마이페이지 > 오픈API > 인증키 발급현황에서 **Decoding 버전** 키 확인 →
      `.env`의 `MOLIT_API_KEY`에 입력 → `python -m scripts.collect_real_estate --days 30`로 검증.

- [ ] **이메일 발송 실제 SMTP 자격증명으로 라이브 테스트 — 사용자 확인 필요**
      (2026-08-01 구현)
      `src/reports/emailer.py`는 모킹 테스트로 SMTP 프로토콜 흐름(ehlo/starttls/login/sendmail)과
      MIME 조립을 검증했지만, 이 샌드박스에서 로컬 더미 SMTP 서버(`smtpd.DebuggingServer`)로
      실 네트워크 E2E를 시도했을 때 asyncore 이벤트 루프 문제로 완전한 검증은 못했음(TCP는
      연결되나 DATA 단계 타임아웃 — 코드 결함이 아니라 샌드박스 환경 제약으로 판단됨).
      `.env`에 실제 SMTP_HOST/SMTP_USER/SMTP_PASSWORD/REPORT_EMAIL_TO를 입력하고
      `python -m scripts.send_report_email --days 7`로 실제 메일이 도착하는지 1회 확인 필요.

## 참고 (해결됨, 기록용)

- [x] Windows cp949 인코딩으로 `requirements.txt` 파싱 실패 → UTF-8 BOM 추가로 해결
- [x] konlpy JVM 초기화 예외가 ImportError만 잡던 버그 → 모든 예외를 RuntimeError로 래핑
- [x] 프로젝트 경로에 한글 포함 시 JPype `UnsatisfiedLinkError` → 영문 경로로 이동 안내
- [x] VSCode 터미널이 옛 시스템 JAVA_HOME을 들고 있는 문제 → `.env`의 JAVA_HOME이
      런타임에 시스템 값을 덮어쓰도록 수정
- [x] `extract_keywords`/`generate_report`가 각각 다른 시각에 실행되면 period_start가
      마이크로초 단위로 어긋나 매칭 실패 → `src/common/period.py`로 자정 기준 정규화
- [x] 스키마에 컬럼(`keywords.explanation`)을 추가했는데 기존 로컬 DB에는 반영 안
      되던 문제 → `ensure_schema_up_to_date()`로 자동 컬럼 보강
- [x] 코스피/코스닥/원달러환율 ECOS stat_code 미확인 → 사용자가 `scripts/lookup_ecos_table.py`로
      로컬에서 직접 조회(802Y001/731Y001 확인) → `ecos_collector.py` `INDICATOR_PRESETS`에 등록 완료
- [x] **코스피/코스닥 등록 직후 실사용 중 발견**: `python -m scripts.collect_bond --days 30` 실행 시
      `sqlite3.IntegrityError: UNIQUE constraint failed: bond_indicators.indicator_code, bond_indicators.date`
      발생. 원인은 코스피/코스닥이 같은 ECOS stat_code(802Y001)를 공유하고 item_code1만 다른데,
      `indicator_code` 컬럼에 stat_code만 저장해서 (indicator_code, date) 유니크 제약에 충돌했기
      때문. `ecos_collector.py`에서 `indicator_code`를 `{stat_code}_{item_code1}` 조합으로 저장하도록
      수정해 해결 (트랜잭션 전체가 롤백되는 구조라 실제 DB에는 반영되지 않고 실패했으므로 데이터
      정리는 불필요). 단, 이 수정 전에 이미 수집된 `기준금리`(base_rate) 기존 행은 `indicator_code`가
      여전히 옛 형식(`722Y001`)이라, 다음 수집부터는 새 형식(`722Y001_0101000`)의 별도 시리즈로 쌓임
      — 리포트에 기준금리가 일시적으로 두 줄로 보일 수 있으나 기능상 문제는 아니며, 신경 쓰인다면
      DB에서 `indicator_code='722Y001'`인 기존 행을 지워도 됨.
- [x] **코스피/코스닥 리포트 표시 깨짐**: 위 수정 직후 실제로 리포트를 생성해보니 "KOSPI지수:
      5593.561980.01.04=100 (...)" 처럼 값과 단위가 깨져 보였음. 원인은 ECOS가 코스피/코스닥
      `UNIT_NAME`으로 실제 단위가 아니라 "1980.01.04=100"(기준시점 설명)을 내려주는데, 코드가
      이 값을 그대로 저장했기 때문. `ecos_collector.py`에서 ECOS가 반환한 UNIT_NAME 대신 항상
      프리셋에 지정한 단위("pt")를 쓰도록 수정. 또한 `save_bond_indicators()`가 값뿐 아니라
      단위가 달라져도 기존 행을 갱신하도록 고쳐서, 이미 잘못 저장된 값도 다음 수집 때 자동
      정정됨(별도 수동 정리 불필요).
- [x] **차트가 5~6개 개별 PNG로 세로 나열되어 산만함(실사용 피드백, 2026-07-31)**: 지표별 개별
      분리는 좋았지만 이미지가 여러 장으로 흩어져 리포트가 길어짐. `charts.py`
      `generate_bond_charts()`를 다시 단일 이미지로 바꾸되, `plt.subplots(rows, cols)`로
      지표당 서브플롯 하나씩 배정하고 최대 3열 격자로 배치(6개면 3x2), `tab10` 색상표로
      서브플롯마다 선 색깔을 다르게 지정. `report_generator.py`도 `bond_chart_path`(단일 경로)로
      복귀, 템플릿도 단일 이미지 임베드로 수정.
- [x] **"주요 공시·뉴스"가 항목마다 개별 요약이라 너무 김(실사용 피드백, 2026-07-31)**: 30건이면
      30개 문단이 나열되는 문제. `summarizer.py`에 `summarize_group()` 추가 — 여러 원문을 한 번에
      받아 개별 나열 없이 전체를 관통하는 종합 요약 하나만 생성(최대 20건까지 입력, 초과분은
      제외해 max_tokens 초과 방지). `report_generator.py`에서 표시 문서를 `content_type`
      (공시/뉴스/정책/공지)별로 묶어 그룹당 `summarize_group()` 호출 1회로 종합 요약 1개씩만
      생성하도록 변경. 부작용: 문서 제목·회사명 등 개별 메타정보는 더 이상 리포트에 표시되지
      않음(요약만 표시) — 필요시 추후 요청 시 재검토.
- [x] **차트가 격자 1장으로 합쳐져 산만함 + 기준금리 그래프 누락(실사용 피드백, 2026-08-01)**:
      `plt.subplots` 격자 합성 이미지 대신 `generate_bond_charts()`가 지표별 개별 PNG를 각각
      생성하도록 재작성(`report_template.md.j2`에서 3열 HTML `<table>`로 배치). 기준금리처럼
      기간 내 값이 1건뿐인 지표도 이제 점 하나짜리 그래프로 포함(예전엔 2건 미만이면 통째로
      제외되어 그래프가 사라졌음).
- [x] **뉴스/공시 종합 요약이 JSON/번호로 감싸여 그대로 노출됨(실사용 피드백, 2026-08-01)**:
      `summarize_group()`이 순수 텍스트를 요청해도 모델이 `{"1": "..."}` 또는 중괄호 없는
      `1: "..."` 형태로 응답하는 경우가 있어, `summarizer.py`에 `_strip_json_wrapper()`를
      추가해 두 변형 모두 순수 텍스트로 정리하도록 후처리.
- [x] **보고서 "주요 공시·뉴스" 목록에 키워드 추출용 필터(exclude-pattern/only-enriched)가
      적용 안 됨(2026-07-29 발견, 2026-08-01 해결)**: `src/common/document_filter.py`로
      필터 로직(`EXCLUDE_PRESETS`, `resolve_exclude_pattern`, `apply_document_filters`)을
      공통 모듈로 분리해 `extract_keywords.py`(기존 로직 이전)와 `report_generator.py`
      양쪽에서 재사용. `generate_report()`/`scripts/generate_report.py`에
      `--exclude-pattern`/`--only-enriched` 옵션 추가.
- [x] **그룹 종합 요약으로 바뀌며 개별 문서 제목·링크가 사라진 트레이드오프(2026-08-01 절충)**:
      `report_generator.py`가 각 `document_groups` 항목에 `titles`(제목/기업명/링크/발행일)
      리스트를 함께 담아 반환하도록 확장. 템플릿에서 `<details>` 접이식 목록으로 종합 요약
      아래 원문 목록을 표시(평소엔 접혀 있어 리포트가 길어지지 않음).
- [x] **기준금리 지표에 옛 형식(`indicator_code='722Y001'`) 잔존 행 + 단위 "연%" 남음
      (2026-08-01 정리)**: `python -m scripts.collect_bond --days 400 --indicators base_rate`로
      전체 기간 재수집해 새 형식(`722Y001_0101000`, 단위 "%") 13건을 확보한 뒤, DB에서
      옛 형식 12건을 직접 삭제. 리포트에 기준금리가 한 줄로만, 올바른 단위로 표시됨을 확인.
- [x] **법령 개정이유 추출이 실사용 시 100% 실패(2026-08-01 라이브 검증 중 발견)**: 365일치
      15건을 실제 LAW_API_KEY로 수집했더니 개정이유가 전부 None(메타정보로 대체)이었음.
      법령상세링크가 실제로는 `<iframe>`으로 본문을 감싼 래퍼 HTML만 반환하고, 그 iframe이
      가리키는 본문 페이지에도 "제·개정이유"는 없이 별도 엔드포인트(`lsRvsDocInfoR.do`)에만
      있다는 걸 페이지 구조를 직접 열어보고 확인. `law_collector.py`를 2단계 요청 방식으로
      재작성해 15/15건 추출 성공으로 검증 완료.
- [x] **이메일 자동 발송 추가 (2026-08-01)**: `src/reports/emailer.py` 신규 —
      Markdown → HTML 이메일 변환 + 차트 이미지 cid 인라인 첨부 + SMTP 발송.
      `scripts/send_report_email.py`(수동 발송 CLI), `src/scheduler/jobs.py`에
      `_maybe_email_report()` 훅 연결(SMTP_HOST/REPORT_EMAIL_TO 미설정 시 자동 스킵).
      모킹 테스트로 SMTP 프로토콜 흐름 검증(22건). 로컬 더미 SMTP 서버로 실 네트워크
      E2E는 샌드박스 제약으로 못함 — 실 SMTP 자격증명으로 라이브 테스트 필요(대기 중 항목 참고).
- [x] **웹 대시보드 추가 (2026-08-01)**: `src/web/dashboard.py`(Flask) 신규 — `reports`
      테이블 기반 목록/상세 렌더링 + 차트 이미지 서빙. `scripts/run_dashboard.py`로 실행.
      실제 Flask 개발 서버를 띄워 진짜 HTTP 요청으로 목록/상세/이미지/404 전부 라이브 검증 완료.
