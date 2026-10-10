"""Owner-only POSIX storage helpers; Windows ACLs require deployment controls."""
import os
import stat
from pathlib import Path


def private_directory(path: Path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Storage directory must be a real directory")
    if os.name == "posix":
        info = path.stat()
        if info.st_uid != os.getuid():
            raise PermissionError("Storage directory is not owned by the current user")
        path.chmod(0o700)


def private_file(path: Path):
    # A trusted parent prevents another local user replacing the file after checks.
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("Database parent must be an existing real directory")
    if os.name == "posix":
        info = path.parent.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise PermissionError("Database parent must be owned by you and not writable by others")
    if path.is_symlink():
        raise ValueError("Symlink database files are not allowed")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Database must be a regular file")
        if os.name == "posix":
            if info.st_uid != os.getuid():
                raise PermissionError("Database is not owned by the current user")
            os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
