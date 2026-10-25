"""Race-safe remote file reads used by both SSH authentication transports.

The program walks directory descriptors and opens every component with NOFOLLOW.
It reads the resulting file descriptor rather than reopening a checked pathname.
PTY servers carry bounded, base64-encoded lines with an explicit success marker.
"""
from __future__ import annotations

import base64
import shlex
from pathlib import PurePosixPath

CHECKED_READ_CHUNK_BYTES = 12 * 1024

_REMOTE_READER = r'''
import base64, os, stat, sys
root, relative, maximum, token = sys.argv[1:]
maximum = int(maximum)
descriptor = None
try:
    directories = root.split("/")[1:] + relative.split("/")[:-1]
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    for component in directories:
        if not component or component in (".", ".."):
            raise ValueError("invalid path component")
        child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
        os.close(descriptor)
        descriptor = child
    handle = os.open(relative.split("/")[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
    os.close(descriptor)
    descriptor = handle
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
        raise ValueError("unsafe output file or size")
    if token:
        print("B:" + token, flush=True)
    total = 0
    while True:
        chunk = os.read(descriptor, min(12288, maximum - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > maximum:
            raise ValueError("output limit exceeded")
        if token:
            print("D:" + base64.b64encode(chunk).decode("ascii"), flush=True)
        else:
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    if token:
        print("E:" + token, flush=True)
except Exception:
    if token:
        print("F:" + token, flush=True)
    else:
        sys.stderr.write("checked_remote_read_failed\n")
    sys.exit(1)
finally:
    if descriptor is not None:
        os.close(descriptor)
'''


def checked_reader_command(root: str, relative: str, maximum: int, *, token: str = "") -> str:
    root_path, relative_path = PurePosixPath(root), PurePosixPath(relative)
    if (
        not root_path.is_absolute() or root == "/" or ".." in root_path.parts
        or not relative_path.parts or relative_path.is_absolute() or ".." in relative_path.parts
        or relative in {".", ".."} or "\\" in relative
        or any(ord(character) < 32 for character in root + relative)
        or isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 0
    ):
        raise ValueError("checked_remote_read_arguments_invalid")
    encoded = base64.b64encode(_REMOTE_READER.encode()).decode("ascii")
    program = f"import base64;exec(base64.b64decode({encoded!r}))"
    return " ".join(shlex.quote(value) for value in ("python3", "-c", program, str(root_path), str(relative_path), str(maximum), token))
