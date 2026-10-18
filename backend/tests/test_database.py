import sqlite3
from pathlib import Path

from wmrm.persistence.database import Database


def test_create_schema_upgrades_existing_tasks_table_with_result_json(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE tasks (
                id VARCHAR(36) PRIMARY KEY,
                plan_id VARCHAR(36) NOT NULL,
                status VARCHAR(32) NOT NULL,
                stage VARCHAR(64) NOT NULL,
                progress FLOAT NOT NULL,
                error_json TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )

    database = Database(database_path)
    database.create_schema()
    database.create_schema()

    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
    assert "result_json" in columns
