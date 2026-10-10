import re
import os
import sqlite3
from uuid import uuid4
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from yaml import safe_load
from pathlib import Path
from platformdirs import user_data_dir
from dooit.api import Todo, Workspace, manager
from dooit.utils.cli_logger import logger
from dooit.utils.database import delete_all_data

BASE_PATH = Path(user_data_dir("dooit"))
operations = []


def parse_recurrence(recurrence: str) -> timedelta:
    DURATION_LEGEND = {
        "m": "minute",
        "h": "hour",
        "d": "day",
        "w": "week",
    }

    def split_duration(duration: str) -> Tuple[str, str]:
        if re.match(r"^(\d+)[mhdw]$", duration):
            return duration[-1], duration[:-1]
        else:
            raise ValueError("Invalid recurrence format")

    sign, frequency = split_duration(recurrence)
    frequency = int(frequency)
    return timedelta(**{f"{DURATION_LEGEND[sign]}s": frequency})


def parse_due(due: str) -> Optional[datetime]:
    if due == "none":
        return None

    due_float = float(due)
    return datetime.fromtimestamp(due_float)


class Migrator2to3:
    old_location = BASE_PATH / "todo.yaml"
    new_location = BASE_PATH / "dooit.db"

    @classmethod
    def check_for_old_data(cls):
        if not cls.old_location.exists():
            return False

        return True

    def load_old(self):
        with self.old_location.open() as f:
            return safe_load(f)

    def backup_old_config(self):
        backup_location = self.old_location.with_name(self.old_location.name + "." + uuid4().hex + ".bak")
        fd = os.open(backup_location, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as backup:
            backup.write(self.old_location.read_bytes())
        logger.success(f"Legacy backup created: {backup_location}")
        return backup_location

    def backup_database(self):
        backup_location = self.new_location.with_name(self.new_location.name + "." + uuid4().hex + ".bak")
        from dooit.utils.private_files import private_file

        private_file(backup_location)
        try:
            with sqlite3.connect(str(self.new_location)) as source:
                with sqlite3.connect(str(backup_location)) as target:
                    source.backup(target)
        except Exception:
            backup_location.unlink(missing_ok=True)
            raise
        logger.success(f"Database backup created: {backup_location}")
        return backup_location

    def migrate(self):
        if not self.check_for_old_data():
            logger.error("No old data found")
            return False

        existed = self.new_location.exists()
        try:
            # Read and validate the top-level container before touching destination rows.
            data = self.load_old()
            if not isinstance(data, list):
                raise ValueError("Legacy data must be a list of workspaces")
            if existed:
                confirm = logger.console.input(
                    "Database already exists. Back it up and replace its data? (y/n): "
                )
                if confirm.lower() != "y":
                    logger.error("Migration aborted")
                    return False
            self.backup_old_config()
            if existed:
                # Check the destination without following final-component symlinks.
                from dooit.utils.private_files import private_file

                private_file(self.new_location)
                self.backup_database()
            manager.connect(str(self.new_location))
            with manager.transaction():
                if existed:
                    delete_all_data(manager.session, commit=False)
                for workspace in data:
                    self.create_workspace(workspace)
        except Exception as e:
            logger.error(f"Migration failed; row changes rolled back: {e}")
            return False

        # Cleanup is separate from commit: a cleanup failure must not imply rollback.
        try:
            self.old_location.unlink()
        except OSError as e:
            logger.warn(f"Migration committed, but legacy file cleanup failed: {e}")
        logger.success("Migration committed. Backups retained.")
        return True

    # ------------------------------------------------

    def create_workspace(self, data, parent=None):
        description = data.get("description")
        child_workspaces = data.get("workspaces", [])
        todos = data.get("todos", [])

        workspace = Workspace(description=description, parent_workspace=parent)
        workspace.save()

        for child in child_workspaces:
            self.create_workspace(child, parent=workspace)

        for child in todos:
            self.create_todo(child, parent_workspace=workspace)

    def create_todo(self, data: List, parent_todo=None, parent_workspace=None):
        self_data = data[0]
        if len(data) == 1:
            children_data = []
        else:
            children_data = data[1]

        description = self_data.get("description")
        pending = self_data.get("status") != "COMPLETED"
        urgency = self_data.get("urgency")
        due = self_data.get("due")
        effort = self_data.get("effort")
        recurrence = self_data.get("recurrence")

        todo = Todo(
            parent_todo=parent_todo,
            parent_workspace=parent_workspace,
            description=description,
            pending=pending,
            urgency=urgency,
            due=parse_due(due),
            effort=int(effort) if effort else None,
            recurrence=parse_recurrence(recurrence) if recurrence else None,
        )
        todo.save()

        for data in children_data:
            self.create_todo(
                data,
                parent_todo=todo,
            )


if __name__ == "__main__":
    m = Migrator2to3()
    if m.check_for_old_data():
        m.migrate()
