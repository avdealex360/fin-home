from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.db import Base
from app.models import AppUser
from app.serializers import user_dict


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_appuser_has_telegram_id_and_serializes(db):
    u = AppUser(name="Леша", telegram_id="12345")
    db.add(u)
    db.commit()
    d = user_dict(u)
    assert d["telegram_id"] == "12345"
