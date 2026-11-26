"""Cooperative, non-blocking ownership of a writable chain directory."""

import errno
import os
from contextlib import contextmanager
from pathlib import Path


class StateDirectoryBusyError(OSError):
    """Another owner holds the directory lock."""


@contextmanager
def state_directory_lock(directory: str | Path):
    """Hold an OS lock for the entire writer lifetime, not merely a file write.

    Keep the lock file in place: deleting it could let another process lock a
    different inode. Closing the handle (including process death) releases
    ownership. All cooperating writers must use this same canonical directory.
    """
    directory = Path(directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ".qchain-state.lock"
    with path.open("a+b") as handle:
        try:
            if os.name == "posix":
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            elif os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                raise OSError("State directory locking is unsupported on this platform.")
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, errno.EDEADLK):
                raise StateDirectoryBusyError(
                    f"State directory is already in use: {directory}"
                ) from error
            raise
        # Closing the handle releases the lock even if startup or a command fails.
        yield directory
