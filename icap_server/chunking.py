"""ICAP chunked body encoding and decoding (RFC 3507 Section 4.5)."""

from __future__ import annotations

_CRLF = b"\r\n"


def decode_chunked_body(data: bytes) -> tuple[bytes, bool]:
    """
    Decode HTTP/ICAP chunked body.

    Returns (decoded_body, has_ieof).
    """
    offset = 0
    chunks: list[bytes] = []
    has_ieof = False

    while offset < len(data):
        line_end = data.find(_CRLF, offset)
        if line_end == -1:
            break

        chunk_size_line = data[offset:line_end].decode("ascii", errors="replace")
        extensions = ""
        if ";" in chunk_size_line:
            chunk_size_line, extensions = chunk_size_line.split(";", 1)
            if "ieof" in extensions.lower():
                has_ieof = True

        try:
            chunk_size = int(chunk_size_line.strip(), 16)
        except ValueError:
            break

        offset = line_end + len(_CRLF)
        if chunk_size == 0:
            break

        chunk_end = offset + chunk_size
        chunks.append(data[offset:chunk_end])
        offset = chunk_end + len(_CRLF)

    return b"".join(chunks), has_ieof


def encode_chunked_body(body: bytes, ieof: bool = False) -> bytes:
    """Encode body using chunked transfer coding."""
    if not body:
        terminator = b"0; ieof\r\n\r\n" if ieof else b"0\r\n\r\n"
        return terminator

    lines = [f"{len(body):x}\r\n".encode("ascii"), body, _CRLF]
    if ieof:
        lines.append(b"0; ieof\r\n\r\n")
    else:
        lines.append(b"0\r\n\r\n")
    return b"".join(lines)


def extract_body_from_section(section: bytes) -> tuple[bytes, bool]:
    """
    Extract body bytes from an encapsulated section.

    Handles both Content-Length and chunked encodings.
    """
    header_block, remainder = _split_headers(section)
    _, headers = _parse_headers(header_block)
    transfer_encoding = headers.get("transfer-encoding", "").lower()
    content_length = headers.get("content-length")

    if "chunked" in transfer_encoding:
        return decode_chunked_body(remainder)

    if content_length is not None:
        try:
            length = int(content_length)
        except ValueError:
            length = len(remainder)
        return remainder[:length], False

    return remainder, False


def _split_headers(data: bytes) -> tuple[bytes, bytes]:
    marker = b"\r\n\r\n"
    idx = data.find(marker)
    if idx == -1:
        return data, b""
    end = idx + len(marker)
    return data[:end], data[end:]


def _parse_headers(header_block: bytes) -> tuple[str, dict[str, str]]:
    text = header_block.decode("latin-1", errors="replace")
    lines = text.split("\r\n")
    if not lines:
        return "", {}
    start_line = lines[0]
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    return start_line, headers
