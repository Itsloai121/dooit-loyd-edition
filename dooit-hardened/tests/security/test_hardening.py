"""Regression tests supplied with the patch; NOT RUN during this source-only review."""
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from dooit.api import Workspace, manager
from dooit.ui.api.loader import temporary_sys_path
from dooit.utils.css_manager import CssManager
from dooit.utils.date_parser import parse
from dooit.utils.private_files import private_file


@pytest.mark.parametrize("identifier", ["../escape", "/absolute", r"..\escape", "", "a/b", "a" * 129])
def test_css_id_cannot_escape(tmp_path, identifier):
    css = CssManager(cache_path=tmp_path)
    with pytest.raises(ValueError):
        css.inject_css("x {}", identifier)
    with pytest.raises(ValueError):
        css.unject_css(identifier)
    with pytest.raises(ValueError):
        css.is_active(identifier)


def test_css_symlink_rejected(tmp_path):
    if os.name != "posix":
        pytest.skip("POSIX symlink test")
    css = CssManager(cache_path=tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("unchanged")
    (css.stylesheets / "linked.tcss").symlink_to(outside)
    with pytest.raises(ValueError):
        css.inject_css("overwrite", "linked")
    assert outside.read_text() == "unchanged"


def test_temporary_sys_path_restores_existing_entry(tmp_path):
    original = sys.path[:]
    parent = str(tmp_path.absolute())
    sys.path.append(parent)
    expected = sys.path[:]
    try:
        with temporary_sys_path(tmp_path / "config.py"):
            pass
        assert sys.path == expected
        with pytest.raises(RuntimeError):
            with temporary_sys_path(tmp_path / "config.py"):
                raise RuntimeError("test")
        assert sys.path == expected
    finally:
        sys.path[:] = original


@pytest.mark.parametrize("family,kind", [(socket.AF_INET, socket.SOCK_STREAM), (socket.AF_INET, socket.SOCK_DGRAM), (socket.AF_INET6, socket.SOCK_STREAM), (socket.AF_INET6, socket.SOCK_DGRAM)])
def test_python_ip_sockets_denied(family, kind):
    code = f'''from dooit.utils.network_policy import install_network_policy
import socket
install_network_policy()
try:
    socket.socket({int(family)}, {int(kind)})
except PermissionError:
    print("DENIED")
else:
    raise SystemExit("network policy failed")
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "DENIED" in result.stdout


def test_dns_denied():
    code = '''from dooit.utils.network_policy import install_network_policy
import socket
install_network_policy()
try:
    socket.getaddrinfo("localhost", 80)
except PermissionError:
    print("DENIED")
else:
    raise SystemExit("DNS policy failed")
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_config_scan_uses_only_defaults():
    from dooit.ui.api import plug
    plugin = plug.PluginManager(SimpleNamespace(app=None), config=Path("untrusted.py"))
    with patch.object(plug, "load_file") as load:
        plugin.scan()
    load.assert_called_once_with(plugin, plug.DEFAULT_CONFIG)


def test_private_database_mode_and_symlink(tmp_path):
    if os.name != "posix":
        pytest.skip("Windows requires ACL verification")
    path = tmp_path / "data.db"
    private_file(path)
    assert path.stat().st_mode & 0o777 == 0o600
    link = tmp_path / "linked.db"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        private_file(link)


def test_date_overflow_returns_invalid():
    assert parse("999999999999999999999999-01-01") == (None, False)


def test_workspace_order_is_parent_scoped():
    manager.connect(":memory:")
    try:
        a, b = Workspace(description="A"), Workspace(description="B")
        a.save()
        b.save()
        ca, cb = a.add_workspace(), b.add_workspace()
        old_order = cb.order_index
        ca.add_sibling()
        manager.session.expire_all()
        assert cb.order_index == old_order
    finally:
        manager.session.close()
        manager.engine.dispose()


def test_todo_order_is_parent_scoped():
    manager.connect(":memory:")
    try:
        a, b = Workspace(description="A"), Workspace(description="B")
        a.save()
        b.save()
        ta, tb = a.add_todo(), b.add_todo()
        old_order = tb.order_index
        ta.add_sibling()
        manager.session.expire_all()
        assert tb.order_index == old_order
    finally:
        manager.session.close()
        manager.engine.dispose()


def test_atomic_row_rollback():
    manager.connect(":memory:")
    try:
        original = Workspace(description="keep")
        original.save()
        with pytest.raises(ValueError):
            with manager.transaction():
                original.drop()
                Workspace(description="partial").save()
                raise ValueError("malformed legacy record")
        assert [w.description for w in Workspace.all()] == ["keep"]
    finally:
        manager.session.close()
        manager.engine.dispose()
