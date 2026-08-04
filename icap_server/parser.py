"""ICAP message parser (RFC 3507)."""

from __future__ import annotations

import re

from .chunking import extract_body_from_section
from .constants import (
    ENTITY_NULL_BODY,
    ENTITY_OPT_BODY,
    ENTITY_REQ_BODY,
    ENTITY_REQ_HDR,
    ENTITY_RES_BODY,
    ENTITY_RES_HDR,
)
from .http_utils import parse_http_message
from .models import EncapsulatedContent, EncapsulatedEntity, HttpMessage, IcapRequest

_CRLF = b"\r\n"
_HEADER_END = b"\r\n\r\n"


def parse_header_block(data: bytes) -> tuple[dict[str, str], bytes]:
    """Parse ICAP/HTTP headers from bytes, returning headers and remainder."""
    header_block, remainder = _split_header_block(data)
    text = header_block.decode("latin-1", errors="replace")
    lines = text.split("\r\n")

    headers: dict[str, str] = {}
    current_name: str | None = None
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

    return headers, remainder


def parse_encapsulated_header(value: str) -> list[EncapsulatedEntity]:
    """Parse Encapsulated header value into ordered entities."""
    entities: list[EncapsulatedEntity] = []
    for part in value.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        name, offset_text = part.split("=", 1)
        entities.append(EncapsulatedEntity(name=name.strip(), offset=int(offset_text.strip())))
    return entities


def parse_request_line(line: str) -> tuple[str, str, str]:
    """Parse ICAP request line: METHOD uri ICAP/1.0"""
    parts = line.strip().split(" ", 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid ICAP request line: {line!r}")
    return parts[0], parts[1], parts[2]


def parse_icap_request(data: bytes) -> IcapRequest:
    """Parse a complete ICAP request from raw bytes."""
    header_block, body = _split_header_block(data)
    text = header_block.decode("latin-1", errors="replace")
    lines = text.split("\r\n")
    if not lines:
        raise ValueError("Empty ICAP request")

    method, uri, version = parse_request_line(lines[0])
    headers, _ = parse_header_block(header_block)

    encapsulated_value = headers.get("encapsulated", "")
    encapsulated = parse_encapsulated_header(encapsulated_value) if encapsulated_value else []

    request = IcapRequest(
        method=method,
        uri=uri,
        version=version,
        headers=headers,
        encapsulated=encapsulated,
        body=body,
        raw_request_line=lines[0],
    )
    request.content = extract_encapsulated_content(body, encapsulated)
    return request


def extract_encapsulated_content(
    body: bytes, encapsulated: list[EncapsulatedEntity]
) -> EncapsulatedContent:
    """Extract encapsulated HTTP messages from ICAP body using offsets."""
    content = EncapsulatedContent()
    if not encapsulated:
        return content

    sections: dict[str, bytes] = {}
    for index, entity in enumerate(encapsulated):
        start = entity.offset
        end = encapsulated[index + 1].offset if index + 1 < len(encapsulated) else len(body)
        sections[entity.name] = body[start:end]

    if ENTITY_REQ_HDR in sections:
        section = sections[ENTITY_REQ_HDR]
        if ENTITY_REQ_BODY in sections or ENTITY_NULL_BODY in sections:
            body_key = ENTITY_REQ_BODY if ENTITY_REQ_BODY in sections else ENTITY_NULL_BODY
            section = section + sections[body_key]
        parsed = _parse_http_section(section)
        content.request = parsed.message
        content.has_ieof = content.has_ieof or parsed.has_ieof

    if ENTITY_RES_HDR in sections:
        section = sections[ENTITY_RES_HDR]
        if ENTITY_RES_BODY in sections or ENTITY_NULL_BODY in sections:
            body_key = ENTITY_RES_BODY if ENTITY_RES_BODY in sections else ENTITY_NULL_BODY
            section = section + sections[body_key]
        parsed = _parse_http_section(section)
        content.response = parsed.message
        content.has_ieof = content.has_ieof or parsed.has_ieof

    if ENTITY_OPT_BODY in sections:
        content.opt_body = sections[ENTITY_OPT_BODY]

    return content


class _ParsedSection:
    def __init__(self, message: HttpMessage, has_ieof: bool = False):
        self.message = message
        self.has_ieof = has_ieof


def _parse_http_section(section: bytes) -> _ParsedSection:
    message = parse_http_message(section)
    body, has_ieof = extract_body_from_section(section)
    message.body = body
    return _ParsedSection(message=message, has_ieof=has_ieof)


def _split_header_block(data: bytes) -> tuple[bytes, bytes]:
    idx = data.find(_HEADER_END)
    if idx == -1:
        return data, b""
    end = idx + len(_HEADER_END)
    return data[:end], data[end:]


def is_complete_icap_message(buffer: bytes) -> bool:
    """Return True when buffer contains a full ICAP request (best effort)."""
    try:
        header_block, icap_body = _split_header_block(buffer)
        if b"\r\n\r\n" not in header_block:
            return False

        headers, _ = parse_header_block(header_block)
        encapsulated = parse_encapsulated_header(headers.get("encapsulated", ""))
        if not encapsulated:
            return True

        last = encapsulated[-1]
        if last.name in (ENTITY_NULL_BODY, ENTITY_OPT_BODY):
            return len(icap_body) >= last.offset

        if len(icap_body) < last.offset:
            return False

        return _encapsulated_sections_complete(icap_body, encapsulated)
    except (ValueError, IndexError):
        return False


def _encapsulated_sections_complete(
    icap_body: bytes, encapsulated: list[EncapsulatedEntity]
) -> bool:
    """Verify all encapsulated HTTP sections with bodies are fully received."""
    entity_names = [entity.name for entity in encapsulated]

    if ENTITY_REQ_BODY in entity_names:
        req_hdr_offset = _entity_offset(encapsulated, ENTITY_REQ_HDR)
        req_body_offset = _entity_offset(encapsulated, ENTITY_REQ_BODY)
        if not _headers_and_body_complete(
            icap_body[req_hdr_offset:req_body_offset],
            icap_body[req_body_offset:],
        ):
            return False

    if ENTITY_RES_BODY in entity_names:
        res_hdr_offset = _entity_offset(encapsulated, ENTITY_RES_HDR)
        res_body_offset = _entity_offset(encapsulated, ENTITY_RES_BODY)
        if not _headers_and_body_complete(
            icap_body[res_hdr_offset:res_body_offset],
            icap_body[res_body_offset:],
        ):
            return False

    return True


def _entity_offset(encapsulated: list[EncapsulatedEntity], name: str) -> int:
    for entity in encapsulated:
        if entity.name == name:
            return entity.offset
    raise ValueError(f"Missing encapsulated entity: {name}")


def _headers_and_body_complete(header_section: bytes, body_section: bytes) -> bool:
    """Check HTTP header section declares a body and body_section has all bytes."""
    from .http_utils import parse_headers

    _, headers = parse_headers(header_section)
    transfer_encoding = headers.get("transfer-encoding", "").lower()

    if "chunked" in transfer_encoding:
        combined = header_section + body_section
        _, remainder = _split_header_block(combined)
        return _chunked_body_complete(remainder)

    if "content-length" in headers:
        try:
            expected = int(headers["content-length"])
        except ValueError:
            return False
        return len(body_section) >= expected

    return True


def _chunked_body_complete(data: bytes) -> bool:
    if not data:
        return False
    return bool(re.search(rb"0(?:;[^\r\n]*)?\r\n\r\n", data))
