from pathlib import Path
from platformdirs import user_data_dir

ROOT_FOLDER = Path(user_data_dir("dooit"))
DATABASE_FILE = ROOT_FOLDER / "dooit.db"
DATABASE_CONN_STRING = f"sqlite:///{DATABASE_FILE}"

from dooit.utils.private_files import private_directory

private_directory(DATABASE_FILE.parent)
