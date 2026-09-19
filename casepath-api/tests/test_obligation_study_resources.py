"""Credit-ledger transactions must not retain database handles between requests."""
import sqlite3

import pytest

from casepath_api.obligation_control.study_v1.journal import Journal


def test_completed_journal_transaction_closes_its_connection(tmp_path):
    journal = Journal(tmp_path / "study.sqlite3")
    with journal.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 0
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")


def test_failed_journal_transaction_rolls_back_and_closes(tmp_path):
    journal = Journal(tmp_path / "study.sqlite3")
    with pytest.raises(RuntimeError, match="interrupted"):
        with journal.connect() as connection:
            connection.execute(
                "INSERT INTO studies VALUES(?,?,?,?,?)",
                ("fixture", "hash", "{}", "1", "engineering_fixture"),
            )
            raise RuntimeError("interrupted")
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")
    with journal.connect() as recovered:
        assert recovered.execute("SELECT COUNT(*) FROM studies").fetchone()[0] == 0
