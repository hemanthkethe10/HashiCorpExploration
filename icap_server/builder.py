"""ICAP response builder (RFC 3507)."""

from __future__ import annotations

from email.utils import formatdate

from .chunking import encode_chunked_body
from .constants import (
    ENTITY_NULL_BODY,
    ENTITY_OPT_BODY,
    ENTITY_REQ_BODY,
    ENTITY_REQ_HDR,
    ENTITY_RES_BODY,
    ENTITY_RES_HDR,
    ICAP_VERSION,
    STATUS_CONTINUE,
    STATUS_NO_CONTENT,
    STATUS_OK,
)
from .http_utils import serialize_http_message
from .models import HttpMessage, IcapResponse


def build_options_response(
    *,
    service_name: str,
    service_id: str,
    istag: str,
    methods: list[str],
    options_ttl: int,
    max_connections: int,
    preview_size: int,
) -> bytes:
    """Build OPTIONS response advertising server capabilities."""
    opt_body = (
        f"Service: {service_name}\n"
        f"Methods: {', '.join(methods)}\n"
        f"Preview: {preview_size}\n"
    ).encode("utf-8")

    body_parts = [opt_body]
    encapsulated = _build_encapsulated_header([(ENTITY_OPT_BODY, 0)])
    headers = {
        "Methods": ", ".join(methods),
        "Service": service_name,
        "Service-ID": service_id,
        "ISTag": f'"{istag}"',
        "Encapsulated": encapsulated,
        "Opt-Body-Type": "text/plain",
        "Options-TTL": str(options_ttl),
        "Max-Connections": str(max_connections),
        "Preview": str(preview_size),
        "Date": formatdate(usegmt=True),
    }
    return _build_response(STATUS_OK, "OK", headers, b"".join(body_parts))


def build_204_response(istag: str) -> bytes:
    """Build 204 No modifications needed response."""
    headers = {
        "ISTag": f'"{istag}"',
        "Encapsulated": _build_encapsulated_header([(ENTITY_NULL_BODY, 0)]),
    }
    return _build_response(STATUS_NO_CONTENT, "No modifications needed", headers, b"")


def build_100_continue(istag: str) -> bytes:
    """Build 100 Continue response for preview extension."""
    headers = {
        "ISTag": f'"{istag}"',
        "Encapsulated": _build_encapsulated_header([(ENTITY_NULL_BODY, 0)]),
    }
    return _build_response(STATUS_CONTINUE, "Continue", headers, b"")


def build_reqmod_modified_response(
    request: HttpMessage,
    istag: str,
    *,
    use_chunking: bool = False,
    ieof: bool = False,
) -> bytes:
    """Return ICAP 200 response with modified encapsulated HTTP request."""
    return _build_modified_http_response(
        request,
        istag,
        entity_hdr=ENTITY_REQ_HDR,
        entity_body=ENTITY_REQ_BODY,
        use_chunking=use_chunking,
        ieof=ieof,
    )


def build_respmod_modified_response(
    response: HttpMessage,
    istag: str,
    *,
    use_chunking: bool = False,
    ieof: bool = False,
) -> bytes:
    """Return ICAP 200 response with modified encapsulated HTTP response."""
    return _build_modified_http_response(
        response,
        istag,
        entity_hdr=ENTITY_RES_HDR,
        entity_body=ENTITY_RES_BODY,
        use_chunking=use_chunking,
        ieof=ieof,
    )


def build_respmod_block_page(
    original_response: HttpMessage,
    istag: str,
    reason: str,
) -> bytes:
    """Replace encapsulated HTTP response with a block/warning page."""
    body = (
        "<html><body>"
        f"<h1>Content Blocked by ICAP</h1><p>{reason}</p>"
        "</body></html>"
    ).encode("utf-8")

    blocked = HttpMessage(
        start_line="HTTP/1.1 403 Forbidden",
        headers={
            "content-type": "text/html; charset=utf-8",
            "connection": "close",
            "x-icap-blocked": "true",
        },
        body=body,
    )
    return build_respmod_modified_response(blocked, istag)


def _build_modified_http_response(
    message: HttpMessage,
    istag: str,
    *,
    entity_hdr: str,
    entity_body: str,
    use_chunking: bool,
    ieof: bool,
) -> bytes:
    if use_chunking:
        hdr_bytes = _serialize_headers_only(message)
        body_bytes = encode_chunked_body(message.body, ieof=ieof)
        req_hdr_offset = 0
        req_body_offset = len(hdr_bytes)
        encapsulated = _build_encapsulated_header(
            [(entity_hdr, req_hdr_offset), (entity_body, req_body_offset)]
        )
        icap_body = hdr_bytes + body_bytes
    else:
        serialized = serialize_http_message(message, message.body)
        hdr_end = serialized.find(b"\r\n\r\n")
        if hdr_end == -1:
            raise ValueError("Invalid HTTP message")
        hdr_bytes = serialized[: hdr_end + 4]
        body_bytes = serialized[hdr_end + 4 :]
        encapsulated = _build_encapsulated_header(
            [(entity_hdr, 0), (entity_body, len(hdr_bytes))]
        )
        icap_body = hdr_bytes + body_bytes

    headers = {
        "ISTag": f'"{istag}"',
        "Encapsulated": encapsulated,
    }
    return _build_response(STATUS_OK, "OK", headers, icap_body)


def _serialize_headers_only(message: HttpMessage) -> bytes:
    lines = [message.start_line]
    headers = dict(message.headers)
    headers.pop("content-length", None)
    headers["transfer-encoding"] = "chunked"
    for key, value in headers.items():
        title_key = "-".join(part.capitalize() for part in key.split("-"))
        lines.append(f"{title_key}: {value}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")


def _build_encapsulated_header(entities: list[tuple[str, int]]) -> str:
    return ", ".join(f"{name}={offset}" for name, offset in entities)


def _build_response(status: int, reason: str, headers: dict[str, str], body: bytes) -> bytes:
    response = IcapResponse(
        version=ICAP_VERSION,
        status_code=status,
        reason=reason,
        headers=headers,
        body=body,
    )
    return response.to_bytes()
