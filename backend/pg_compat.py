"""GLITCHLAB_ PostgreSQL compatibility bridge for isolated workspace queries.

This is an incremental adapter, NOT a drop-in replacement for all of main.py:
SQLite schema initialization, legacy routes, auth sqlite exception handling,
and rowid-dependent queries must be migrated before runtime cutover.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import os
import psycopg
from psycopg.rows import dict_row


class CompatRow(dict):
    """Support sqlite3.Row-style access by column label and integer position."""
    def __getitem__(self, key):
        if isinstance(key, int):
            try:
                return list(self.values())[key]
            except IndexError:
                raise IndexError(key) from None
        return super().__getitem__(key)


def qmarks(sql: str) -> str:
    """Translate unquoted SQLite ? placeholders to psycopg %s placeholders."""
    output = []
    state = 'code'
    i = 0
    while i < len(sql):
        ch = sql[i]
        next_ch = sql[i + 1] if i + 1 < len(sql) else ''
        if state == 'code':
            if ch == "'":
                state = 'single'
            elif ch == '"':
                state = 'double'
            elif ch == '-' and next_ch == '-':
                output.extend((ch, next_ch)); i += 2; state = 'line_comment'; continue
            elif ch == '/' and next_ch == '*':
                output.extend((ch, next_ch)); i += 2; state = 'block_comment'; continue
            elif ch == '?':
                output.append('%s'); i += 1; continue
        elif state == 'single':
            if ch == "'":
                if next_ch == "'":
                    output.extend((ch, next_ch)); i += 2; continue
                state = 'code'
        elif state == 'double':
            if ch == '"':
                if next_ch == '"':
                    output.extend((ch, next_ch)); i += 2; continue
                state = 'code'
        elif state == 'line_comment' and ch == '\n':
            state = 'code'
        elif state == 'block_comment' and ch == '*' and next_ch == '/':
            output.extend((ch, next_ch)); i += 2; state = 'code'; continue
        output.append(ch)
        i += 1
    return ''.join(output)


class Result:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount
    @staticmethod
    def _adapt(row):
        return CompatRow(row) if row is not None else None
    def fetchone(self):
        return self._adapt(self.cursor.fetchone())
    def fetchall(self):
        return [self._adapt(row) for row in self.cursor.fetchall()]
    def __iter__(self):
        for row in self.cursor:
            yield self._adapt(row)


class Connection:
    def __init__(self, connection):
        self.raw = connection
    def execute(self, sql: str, params=()):
        if 'rowid' in sql.lower():
            raise RuntimeError('SQLite rowid query must be migrated explicitly before PostgreSQL use')
        if sql.lstrip().upper().startswith('PRAGMA '):
            raise RuntimeError('SQLite PRAGMA cannot run on PostgreSQL')
        cursor = self.raw.execute(qmarks(sql), params)
        return Result(cursor)
    def executescript(self, _):
        raise RuntimeError('SQLite executescript must be replaced with a PostgreSQL migration')


def read_url() -> str:
    """Read a private local file, or DATABASE_URL from environment, never print it."""
    url = os.getenv('DATABASE_URL', '').strip()
    if url:
        return url
    filename = Path(__file__).with_name('.env.postgres.local')
    if not filename.is_file():
        # Allow keeping this helper alongside existing scripts in the backend folder.
        raise RuntimeError('Missing DATABASE_URL or .env.postgres.local beside pg_compat.py')
    for line in filename.read_text(encoding='utf-8').splitlines():
        if line.strip().startswith('DATABASE_URL='):
            return line.split('=', 1)[1].strip().strip('"').strip("'")
    raise RuntimeError('DATABASE_URL not found in .env.postgres.local')


@contextmanager
def pg_db(*, read_only=False):
    """Connections commit writes on success and rollback exceptions."""
    with psycopg.connect(read_url(), row_factory=dict_row, connect_timeout=15) as raw:
        if read_only:
            raw.execute('SET TRANSACTION READ ONLY')
        yield Connection(raw)
