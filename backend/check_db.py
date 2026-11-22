from sqlalchemy import create_engine, text

from app.core.config import settings


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

try:
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT version(), current_database()")
        )

        version, database = result.fetchone()

        print("Database connection successful")
        print("Database:", database)
        print("PostgreSQL:", version.split(",")[0])

except Exception as exc:
    print("Database connection failed")
    print(type(exc).__name__, str(exc))

finally:
    engine.dispose()