"""Data models for ICAP messages and encapsulated HTTP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EncapsulatedEntity:
    name: str
    offset: int


@dataclass
class HttpMessage:
    """Parsed HTTP request or response headers plus optional body bytes."""

    start_line: str
    headers: dict[str, str]
    body: bytes = b""
    raw_headers: bytes = b""

    @property
    def method(self) -> str:
        return self.start_line.split(" ", 1)[0]

    @property
    def uri(self) -> str:
        parts = self.start_line.split(" ", 2)
        return parts[1] if len(parts) > 1 else ""

    @property
    def status_code(self) -> int:
        parts = self.start_line.split(" ", 2)
        if len(parts) < 2:
            return 0
        try:
            return int(parts[1])
        except ValueError:
            return 0

    def get_header(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), default)

    def has_header(self, name: str) -> bool:
        return name.lower() in self.headers


@dataclass
class EncapsulatedContent:
    """HTTP content extracted from an ICAP message body."""

    request: Optional[HttpMessage] = None
    response: Optional[HttpMessage] = None
    opt_body: bytes = b""
    has_ieof: bool = False


@dataclass
class IcapRequest:
    method: str
    uri: str
    version: str
    headers: dict[str, str]
    encapsulated: list[EncapsulatedEntity]
    body: bytes
    content: EncapsulatedContent = field(default_factory=EncapsulatedContent)
    raw_request_line: str = ""

    def get_header(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), default)

    def allows_204(self) -> bool:
        allow = self.get_header("allow", "")
        return "204" in [part.strip() for part in allow.split(",")]

    def preview_size(self) -> Optional[int]:
        preview = self.get_header("preview")
        if not preview:
            return None
        try:
            return int(preview)
        except ValueError:
            return None


@dataclass
class IcapResponse:
    version: str
    status_code: int
    reason: str
    headers: dict[str, str]
    body: bytes = b""

    def to_bytes(self) -> bytes:
        lines = [f"{self.version} {self.status_code} {self.reason}"]
        for key, value in self.headers.items():
            lines.append(f"{key}: {value}")
        header_block = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")
        return header_block + self.body
