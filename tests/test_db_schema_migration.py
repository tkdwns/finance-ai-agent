"""storage/db.py의 ensure_schema_up_to_date (자동 스키마 보강) 테스트."""

import pytest
from sqlalchemy import Column, Integer, String, create_engine, inspect, text
from sqlalchemy.orm import declarative_base

import src.storage.db as db_module


@pytest.fixture()
def temp_engine(monkeypatch):
    """임시 in-memory 엔진을 만들어 db_module.engine을 이 테스트 동안만 바꿔치기한다."""
    engine = create_engine("sqlite:///:memory:")
    monkeypatch.setattr(db_module, "engine", engine)
    return engine


def test_ensure_schema_creates_missing_table(temp_engine):
    Base = declarative_base()

    class Widget(Base):
        __tablename__ = "widgets"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    db_module.ensure_schema_up_to_date(Base)

    inspector = inspect(temp_engine)
    assert "widgets" in inspector.get_table_names()


def test_ensure_schema_adds_missing_column_without_dropping_existing_data(temp_engine):
    """기존 테이블에 새 컬럼을 모델에 추가했을 때, 기존 행 데이터를 유지한 채
    컬럼만 ALTER TABLE로 보강되어야 한다 (이번에 실제로 겪은 버그의 재현 테스트)."""
    # 1) "옛 버전" 스키마로 테이블을 먼저 만들고 데이터를 넣는다
    with temp_engine.begin() as conn:
        conn.execute(text("CREATE TABLE widgets (id INTEGER PRIMARY KEY, name VARCHAR(50))"))
        conn.execute(text("INSERT INTO widgets (id, name) VALUES (1, 'old-widget')"))

    # 2) "새 버전" 모델에는 컬럼이 하나 추가되어 있다
    Base = declarative_base()

    class Widget(Base):
        __tablename__ = "widgets"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))
        description = Column(String(200))  # 새로 추가된 컬럼

    db_module.ensure_schema_up_to_date(Base)

    inspector = inspect(temp_engine)
    columns = {col["name"] for col in inspector.get_columns("widgets")}
    assert "description" in columns

    # 기존 데이터가 그대로 남아있는지 확인
    with temp_engine.connect() as conn:
        row = conn.execute(text("SELECT id, name FROM widgets WHERE id = 1")).fetchone()
    assert row == (1, "old-widget")


def test_ensure_schema_is_idempotent(temp_engine):
    """이미 컬럼이 있는 상태에서 다시 호출해도 에러 없이 통과해야 한다."""
    Base = declarative_base()

    class Widget(Base):
        __tablename__ = "widgets"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    db_module.ensure_schema_up_to_date(Base)
    db_module.ensure_schema_up_to_date(Base)  # 두 번째 호출도 문제없어야 함

    inspector = inspect(temp_engine)
    assert "widgets" in inspector.get_table_names()
