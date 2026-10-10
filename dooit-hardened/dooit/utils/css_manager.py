import sys
import os
import re
from pathlib import Path
from typing import Optional, Type, Union
from platformdirs import user_cache_dir
from dooit.api.theme import DooitThemeBase
from uuid import uuid4

dooit_cache_path = Path(user_cache_dir("dooit"))

if getattr(sys, "frozen", False):
    BASE_PATH = Path(sys._MEIPASS) / "dooit"  # pragma: no cover (binary pkg)
else:
    BASE_PATH = Path(__file__).parent.parent


def generate_random_id():
    return uuid4().hex


class CssManager:
    base_css: Path = BASE_PATH / "ui" / "styles.tcss"
    themes = dict()

    def __init__(
        self,
        theme: DooitThemeBase = DooitThemeBase(),
        cache_path: Path = dooit_cache_path,
    ):
        self.theme: DooitThemeBase = theme
        self.cache_path = cache_path
        self.stylesheets: Path = cache_path / "stylesheets"
        self.css_file: Path = cache_path / "dooit.tcss"

        cache_path.mkdir(parents=True, exist_ok=True)
        if not self.css_file.exists():
            self.write("")

        self.stylesheets.mkdir(
            parents=True,
            exist_ok=True,
        )

    def read_css(self) -> str:
        return self.css_file.read_text()

    def refresh_css(self):
        css = self.theme.to_css()

        # setup base variables
        with open(self.base_css, "r") as f:
            css = css + "\n" + f.read()

        # inject extra stylesheets
        self.stylesheets.mkdir(parents=True, exist_ok=True)
        for sheet in sorted(self.stylesheets.glob("*.tcss")):
            if sheet.is_symlink() or not sheet.is_file():
                raise ValueError("Only regular stylesheet files are allowed")
            with open(sheet, "r", encoding="utf-8") as f:
                css = css + "\n" + f.read()

        self.write(css)

    def add_theme(self, theme: Type[DooitThemeBase]):
        self.themes[theme._name] = theme()
        self.refresh_css()

    def set_theme(self, theme: Union[str, Type[DooitThemeBase]]):
        if isinstance(theme, str):
            self.theme = self.themes.get(theme, DooitThemeBase())
        else:
            self.theme = theme()

        self.refresh_css()

    def _stylesheet_path(self, identifier: str) -> Path:
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identifier):
            raise ValueError("Stylesheet ID must contain only letters, digits, underscores or hyphens")
        candidate = self.stylesheets / f"{identifier}.tcss"
        if candidate.is_symlink():
            raise ValueError("Symlink stylesheets are not allowed")
        return candidate

    def inject_css(self, css: str, _id: Optional[str] = None) -> str:
        uuid = _id or generate_random_id()
        css_file = self._stylesheet_path(uuid)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(css_file, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(css)

        self.refresh_css()
        return uuid

    def unject_css(self, _id: str) -> bool:
        css_file = self._stylesheet_path(_id)

        if not css_file.exists():
            return False

        css_file.unlink()
        self.refresh_css()
        return True

    def is_active(self, _id: str) -> bool:
        return self._stylesheet_path(_id).is_file()

    def write(self, css: str):
        with open(self.css_file, "w") as f:
            f.write(css)

    def cleanup(self):
        for sheet in self.stylesheets.iterdir():
            sheet.unlink()

        self.stylesheets.rmdir()
        self.refresh_css()
