from sqlalchemy.engine import Engine

from app.db.engine import create_session_factory


def get_session_factory(engine: Engine):
    return create_session_factory(engine)
