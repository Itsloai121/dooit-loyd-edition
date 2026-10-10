import os
from pathlib import Path
from contextlib import contextmanager
from typing import Optional
from sqlalchemy import create_engine, URL
from sqlalchemy.orm import Session
from ._vars import DATABASE_FILE


class Manager:
    """
    Class for managing sqlalchemy sessions
    """

    def connect(self, path: Optional[str] = None):
        """
        Connect to database using a file path

        Args:
            path: Path to SQLite database file. Can include ~ for home directory.
        """

        from dooit.api import BaseModel

        path = path or DATABASE_FILE
        path = os.path.expanduser(path)
        if path != ":memory:":
            from dooit.utils.private_files import private_file

            path = str(Path(path).absolute())
            private_file(Path(path))
        connection_url = URL.create("sqlite", database=path)
        if hasattr(self, "session"):
            self.session.close()
            self.engine.dispose()
        self._transaction_depth = 0
        self.engine = create_engine(connection_url)
        self.session = Session(self.engine)

        BaseModel.metadata.create_all(bind=self.engine)
        self._db_last_modified = self._get_db_last_modified()

    def _get_db_last_modified(self) -> Optional[float]:
        database = self.engine.url.database
        assert database is not None

        try:
            return os.path.getmtime(database)
        except OSError:
            return None

    def has_changed(self) -> bool:
        current_last_modified = self._get_db_last_modified()
        if current_last_modified and self._db_last_modified != current_last_modified:
            self._db_last_modified = current_last_modified
            self.session.expire_all()
            return True
        return False

    def delete(self, obj):
        self.session.delete(obj)
        self.commit()

    def save(self, obj):
        self.session.add(obj)
        self.commit()

    def commit(self):
        if self._transaction_depth:
            self.session.flush()
        else:
            try:
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
            self._db_last_modified = self._get_db_last_modified()

    @contextmanager
    def transaction(self):
        if self._transaction_depth:
            raise RuntimeError("Nested migration transactions are not supported")
        self._transaction_depth = 1
        try:
            yield
            self.session.commit()
            self._db_last_modified = self._get_db_last_modified()
        except Exception:
            self.session.rollback()
            raise
        finally:
            self._transaction_depth = 0


manager = Manager()
