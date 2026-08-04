"""HTTP parsing and manipulation helpers."""

from __future__ import annotations

import re
from typing import Optional

from .models import HttpMessage

_CRLF = b"\r\n"
_HEADER_END = b"\r\n\r\n"


def split_header_block(data: bytes) -> tuple[bytes, bytes]:
    """Split raw bytes into header block and remainder."""
    idx = data.find(_HEADER_END)
    if idx == -1:
        return data, b""
    end = idx + len(_HEADER_END)
    return data[:end], data[end:]


def parse_headers(header_block: bytes) -> tuple[str, dict[str, str]]:
    """Parse HTTP-style header block into start line and header dict."""
    text = header_block.decode("latin-1", errors="replace")
    lines = text.split("\r\n")
    if not lines:
        return "", {}

    start_line = lines[0]
    headers: dict[str, str] = {}
    current_name: Optional[str] = None

    for line in lines[1:]:
        if not line:
            continue
        if line.startswith((" ", "\t")) and current_name:
            headers[current_name] += " " + line.strip()
            continue
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        current_name = name.strip().lower()
        headers[current_name] = value.strip()

    return start_line, headers


def parse_http_message(data: bytes) -> HttpMessage:
    """Parse HTTP request/response headers from raw bytes."""
    header_block, remainder = split_header_block(data)
    start_line, headers = parse_headers(header_block)
    return HttpMessage(
        start_line=start_line,
        headers=headers,
        body=remainder,
        raw_headers=header_block,
    )


def serialize_http_message(message: HttpMessage, body: bytes | None = None) -> bytes:
    """Serialize HTTP message with Content-Length body (not chunked)."""
    payload = body if body is not None else message.body
    lines = [message.start_line]
    headers = dict(message.headers)

    headers.pop("transfer-encoding", None)
    headers["content-length"] = str(len(payload))

    for key, value in headers.items():
        title_key = "-".join(part.capitalize() for part in key.split("-"))
        lines.append(f"{title_key}: {value}")
    header_bytes = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    return header_bytes + payload


def set_header(message: HttpMessage, name: str, value: str) -> HttpMessage:
    updated = dict(message.headers)
    updated[name.lower()] = value
    return HttpMessage(
        start_line=message.start_line,
        headers=updated,
        body=message.body,
        raw_headers=message.raw_headers,
    )


def remove_header(message: HttpMessage, name: str) -> HttpMessage:
    updated = dict(message.headers)
    updated.pop(name.lower(), None)
    return HttpMessage(
        start_line=message.start_line,
        headers=updated,
        body=message.body,
        raw_headers=message.raw_headers,
    )


def extract_host_from_uri(uri: str) -> str:
    """Extract hostname from an HTTP or ICAP URI."""
    match = re.match(r"^https?://([^/:]+)", uri, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return ""


def host_in_message(message: HttpMessage) -> str:
    host = message.get_header("host", "")
    if host:
        return host.split(":")[0].lower()
    return extract_host_from_uri(message.uri)
