from database.connection import db_session
from database.models import SCHEMA_SQL


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(SCHEMA_SQL)


if __name__ == "__main__":
    init_db()
    print("Base de datos inicializada.")
