"""SSH transports for the LSF adapter.

Two transports because clusters differ in what they permit:

* :class:`KeySSHTransport` - ``ssh -o BatchMode=yes`` with a key. Preferred.
* :class:`PasswordSSHTransport` - paramiko with a password, for sites whose SSH
  servers do not offer ``publickey`` at all. Such a server also tends to refuse plain
  exec channels, so commands run on a PTY.

A PTY echoes the command back, rewrites newlines as CRLF, and carries login-shell noise
(conda banners, MOTD). Parsing that directly would corrupt ``bjobs`` output, so commands
are wrapped in sentinels and only the text between them is returned. Script bodies are
shipped base64-encoded rather than over stdin, which a PTY would mangle.
"""

from __future__ import annotations

import base64
import io
import re
import shlex
import subprocess
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

_SENTINEL = re.compile(
    r"__BDA_BEGIN_(?P<token>[0-9a-f]{16})__\r?\n(?P<body>.*?)__BDA_END_(?P=token)_(?P<code>\d+)__",
    re.DOTALL,
)


@dataclass(frozen=True)
class SSHResult:
    returncode: int
    stdout: str
    stderr: str


class SSHTransport(Protocol):
    def run(self, command: str, *, check: bool = True, timeout: int = 60) -> SSHResult: ...

    def put_file(self, remote_path: str, content: str) -> None: ...

    # Binary staging. Needed because compute clusters frequently cannot reach the
    # object store directly, so the API moves data over the SSH channel it already has.
    def put_bytes(self, remote_path: str, data: bytes) -> None: ...

    def get_bytes(self, remote_path: str) -> bytes: ...

    # Streaming variants. Whole-object reads are bounded by memory; a structure set or
    # trajectory is not, so bulk transfers use these instead.
    def put_stream(self, remote_path: str, body: Iterator[bytes]) -> None: ...

    def stream(self, remote_path: str, *, chunk_size: int = 1024 * 1024) -> Iterator[bytes]: ...


class KeySSHTransport:
    """Non-interactive key auth over the system ssh client."""

    def __init__(self, host: str, *, key_path: str | None, connect_timeout: int, port: int | None = None) -> None:
        self.host = host
        self.key_path = key_path
        self.connect_timeout = connect_timeout
        self.port = port

    def _argv(self) -> list[str]:
        argv = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={self.connect_timeout}"]
        if self.key_path:
            argv.extend(["-i", self.key_path])
        if self.port:
            argv.extend(["-p", str(self.port)])
        return argv

    def run(self, command: str, *, check: bool = True, timeout: int = 60) -> SSHResult:
        completed = subprocess.run(
            [*self._argv(), self.host, command],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=check,
        )
        return SSHResult(completed.returncode, completed.stdout, completed.stderr)

    def put_file(self, remote_path: str, content: str) -> None:
        self.put_bytes(remote_path, content.encode("utf-8"))

    def put_bytes(self, remote_path: str, data: bytes) -> None:
        subprocess.run(
            [*self._argv(), self.host, f"cat > {shlex.quote(remote_path)}"],
            input=data,
            capture_output=True,
            timeout=600,
            check=True,
        )

    def get_bytes(self, remote_path: str) -> bytes:
        completed = subprocess.run(
            [*self._argv(), self.host, f"cat {shlex.quote(remote_path)}"],
            capture_output=True,
            timeout=600,
            check=True,
        )
        return completed.stdout

    def put_stream(self, remote_path: str, body: Iterator[bytes]) -> None:
        process = subprocess.Popen(
            [*self._argv(), self.host, f"cat > {shlex.quote(remote_path)}"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        assert process.stdin is not None
        try:
            for chunk in body:
                process.stdin.write(chunk)
        finally:
            process.stdin.close()
            code = process.wait(timeout=3600)
        if code != 0:
            raise RuntimeError(f"ssh_put_stream_failed:{code}")

    def stream(self, remote_path: str, *, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        process = subprocess.Popen(
            [*self._argv(), self.host, f"cat {shlex.quote(remote_path)}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        assert process.stdout is not None
        try:
            while chunk := process.stdout.read(chunk_size):
                yield chunk
        finally:
            process.stdout.close()
            if process.wait(timeout=3600) != 0:
                raise RuntimeError("ssh_stream_failed")


class PasswordSSHTransport:
    """Password auth via paramiko, for servers that do not offer publickey.

    The password is read from a file at construction time; it is never placed on a
    command line or in an image layer.
    """

    def __init__(
        self,
        host: str,
        *,
        username: str,
        password: str,
        port: int = 22,
        connect_timeout: int = 10,
    ) -> None:
        self.host = host
        self.username = username
        self._password = password
        self.port = port
        self.connect_timeout = connect_timeout
        self._client: Any = None

    def _connect(self) -> Any:
        import paramiko

        if self._client is not None and self._client.get_transport() and self._client.get_transport().is_active():
            return self._client
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(
            self.host,
            port=self.port,
            username=self.username,
            password=self._password,
            look_for_keys=False,
            allow_agent=False,
            timeout=self.connect_timeout,
        )
        self._client = client
        return client

    def run(self, command: str, *, check: bool = True, timeout: int = 60) -> SSHResult:
        client = self._connect()
        token = uuid.uuid4().hex[:16]
        # Sentinels isolate the command's own output from PTY echo and login-shell noise.
        # The command runs in a subshell, not a brace group: a brace group shares the
        # login shell, so a command containing `exit` would kill the session before the
        # closing sentinel is written and the real exit code would be lost.
        wrapped = (
            f"echo __BDA_BEGIN_{token}__; "
            f"( {command} ) 2>&1; "
            f"__bda_rc=$?; echo __BDA_END_{token}_${{__bda_rc}}__"
        )
        _, stdout, _ = client.exec_command(wrapped, timeout=timeout, get_pty=True)
        raw = stdout.read().decode("utf-8", errors="replace")
        match = _SENTINEL.search(raw)
        if match is None:
            if check:
                raise RuntimeError(f"ssh_output_unparsable:{raw[-400:]}")
            return SSHResult(1, "", raw)
        body = match.group("body").replace("\r\n", "\n")
        code = int(match.group("code"))
        if check and code != 0:
            raise subprocess.CalledProcessError(code, command, output=body, stderr=body)
        # The PTY merges stderr into stdout; callers treat stdout as the payload.
        return SSHResult(code, body, "" if code == 0 else body)

    def put_file(self, remote_path: str, content: str) -> None:
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        self.run(f"printf %s {shlex.quote(encoded)} | base64 -d > {shlex.quote(remote_path)}")

    def _sftp(self):
        return self._connect().open_sftp()

    def put_bytes(self, remote_path: str, data: bytes) -> None:
        # SFTP rather than base64-over-exec: scientific inputs are large enough that a
        # 33% encoding overhead and a single shell command line are not acceptable.
        sftp = self._sftp()
        try:
            sftp.putfo(io.BytesIO(data), remote_path)
        finally:
            sftp.close()

    def get_bytes(self, remote_path: str) -> bytes:
        sftp = self._sftp()
        try:
            with sftp.open(remote_path, "rb") as handle:
                return handle.read()
        finally:
            sftp.close()

    def put_stream(self, remote_path: str, body: Iterator[bytes]) -> None:
        sftp = self._sftp()
        try:
            with sftp.open(remote_path, "wb") as handle:
                for chunk in body:
                    handle.write(chunk)
        finally:
            sftp.close()

    def stream(self, remote_path: str, *, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        sftp = self._sftp()
        try:
            with sftp.open(remote_path, "rb") as handle:
                while chunk := handle.read(chunk_size):
                    yield chunk
        finally:
            sftp.close()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def read_secret(reference: str) -> str:
    """Resolve a credential reference. Only file references are supported.

    Passwords are deliberately not read from environment variables: env is visible in
    ``docker inspect`` and in every child process.
    """
    if not reference.startswith("file:"):
        raise RuntimeError("lsf_password_ref_must_be_file")
    path = Path(reference[len("file:") :]).expanduser()
    secret = path.read_text(encoding="utf-8").strip()
    if not secret:
        raise RuntimeError("lsf_password_empty")
    return secret
