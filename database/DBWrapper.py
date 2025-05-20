import aiosqlite
import sqlite3
from types import TracebackType
from .Tables import all_tables
from .Indices import all_indices
from dataclasses import dataclass
import os

@dataclass
class DBWrapperConnection:
    connection: aiosqlite.Connection

    async def __aenter__(self) -> aiosqlite.Connection:
        db = await self.connection
        return db

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        await self.connection.close()

@dataclass
class DBWrapper:
    db_directory: str
    db_filename: str

    def connect(self):
        def connector() -> sqlite3.Connection:
            db_path = f"{self.db_directory}/{self.db_filename}"
            conn = sqlite3.connect(db_path, isolation_level='DEFERRED')
            return conn

        db_connection = aiosqlite.Connection(connector, iter_chunk_size=64)
        return DBWrapperConnection(db_connection)

    async def create_all_tables(self):
        if not os.path.exists(self.db_directory):
            os.mkdir(self.db_directory)
        async with self.connect() as db:
            for table_query in all_tables:
                await db.execute(table_query)
            for index_query in all_indices:
                await db.execute(index_query)
            await db.commit()