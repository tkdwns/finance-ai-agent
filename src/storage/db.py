"""
데이터베이스 연결 및 세션 관리.

상세 테이블 스키마(models.py)는 다음 단계에서 별도로 설계한다.
이 파일은 SQLAlchemy 엔진/세션의 공통 진입점만 제공한다.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from config.settings import settings

engine = create_engine(settings.database_url, echo=(settings.environment == "development"))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session():
    """with get_session() as session: 형태로 사용."""
    return SessionLocal()


def ensure_schema_up_to_date(base) -> None:
    """
    테이블을 생성하고, 이미 존재하는 테이블에는 모델에만 있고 실제 DB에는 없는
    컬럼을 자동으로 ALTER TABLE로 추가한다.

    `Base.metadata.create_all()`은 없는 테이블만 만들고 기존 테이블의 컬럼 변경은
    반영하지 않는다. 이 프로젝트는 아직 Alembic 같은 정식 마이그레이션 도구 없이
    모델을 계속 수정해나가는 초기 단계라, 스키마에 새 컬럼을 추가할 때마다 기존
    로컬 DB가 깨지는 걸 막기 위한 최소한의 자동 보강 장치다.

    프로덕션/PostgreSQL로 전환하는 시점에는 Alembic 도입을 권장한다.
    """
    base.metadata.create_all(engine)  # 없는 테이블은 새로 생성

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # 방금 새로 생성된 테이블이므로 컬럼 보강 불필요

            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue

                col_type = column.type.compile(dialect=engine.dialect)
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"))
                print(f"[스키마 보강] {table.name}.{column.name} 컬럼을 추가했습니다 (기존 행은 NULL로 채워짐).")
