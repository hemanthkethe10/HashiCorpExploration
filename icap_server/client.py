#!/usr/bin/env python3
"""ICAP test client for local verification."""

from __future__ import annotations

import argparse
import socket
import sys
from typing import Optional


def send_icap_request(host: str, port: int, payload: bytes, timeout: float = 5.0) -> bytes:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(payload)
        chunks: list[bytes] = []
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
        return b"".join(chunks)


def build_options_request(service: str = "all") -> bytes:
    lines = [
        f"OPTIONS icap://{host_placeholder()}/{service} ICAP/1.0",
        f"Host: {host_placeholder()}",
        "User-Agent: icap-test-client/1.0",
        "Connection: close",
        "Encapsulated: null-body=0",
    ]
    return _finalize_icap_message(lines)


def build_reqmod_get_request(
    url: str = "http://example.com/index.html",
    *,
    allow_204: bool = True,
    preview: Optional[int] = None,
) -> bytes:
    http_request = (
        f"GET {url} HTTP/1.1\r\n"
        f"Host: example.com\r\n"
        "Accept: */*\r\n"
        "\r\n"
    )
    body = http_request.encode("ascii")
    hdr_len = len(body)

    lines = [
        "REQMOD icap://127.0.0.1:1344/reqmod ICAP/1.0",
        "Host: 127.0.0.1",
        "User-Agent: icap-test-client/1.0",
        "Connection: close",
    ]
    if allow_204:
        lines.append("Allow: 204")
    if preview is not None:
        lines.append(f"Preview: {preview}")
    lines.append(f"Encapsulated: req-hdr=0, null-body={hdr_len}")
    return _finalize_icap_message(lines, body)


def build_reqmod_post_request(
    url: str = "http://example.com/upload",
    post_body: str = "username=alice&file=data",
) -> bytes:
    content = post_body.encode("utf-8")
    http_headers = (
        f"POST {url} HTTP/1.1\r\n"
        "Host: example.com\r\n"
        "Content-Type: application/x-www-form-urlencoded\r\n"
        f"Content-Length: {len(content)}\r\n"
        "\r\n"
    ).encode("ascii")
    http_body_offset = len(http_headers)
    icap_body = http_headers + content

    lines = [
        "REQMOD icap://127.0.0.1:1344/reqmod ICAP/1.0",
        "Host: 127.0.0.1",
        "User-Agent: icap-test-client/1.0",
        "Connection: close",
        "Allow: 204",
        f"Encapsulated: req-hdr=0, req-body={http_body_offset}",
    ]
    return _finalize_icap_message(lines, icap_body)


def build_respmod_request(
    *,
    response_body: str = "<html><body>Hello ICAP</body></html>",
    include_malware: bool = False,
) -> bytes:
    if include_malware:
        response_body = response_body + " MALWARE_SIGNATURE"

    body_bytes = response_body.encode("utf-8")
    http_request = (
        "GET http://example.com/page HTTP/1.1\r\n"
        "Host: example.com\r\n"
        "\r\n"
    ).encode("ascii")
    req_hdr_len = len(http_request)

    http_response = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/html\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        "\r\n"
    ).encode("ascii")
    res_hdr_offset = req_hdr_len
    res_body_offset = res_hdr_offset + len(http_response)
    icap_body = http_request + http_response + body_bytes

    lines = [
        "RESPMOD icap://127.0.0.1:1344/respmod ICAP/1.0",
        "Host: 127.0.0.1",
        "User-Agent: icap-test-client/1.0",
        "Connection: close",
        "Allow: 204",
        (
            "Encapsulated: req-hdr=0, res-hdr="
            f"{res_hdr_offset}, res-body={res_body_offset}"
        ),
    ]
    return _finalize_icap_message(lines, icap_body)


def build_blocked_domain_reqmod() -> bytes:
    return build_reqmod_get_request("http://malware.example/evil")


def host_placeholder() -> str:
    return "127.0.0.1:1344"


def _finalize_icap_message(header_lines: list[str], body: bytes = b"") -> bytes:
    """Join ICAP headers and append mandatory blank line before body."""
    return ("\r\n".join(header_lines) + "\r\n\r\n").encode("ascii") + body


def print_response(label: str, response: bytes) -> None:
    print(f"\n{'=' * 60}")
    print(label)
    print("=" * 60)
    try:
        print(response.decode("utf-8", errors="replace"))
    except Exception:
        print(response)


def run_all_tests(host: str, port: int) -> int:
    tests = [
        ("OPTIONS", build_options_request()),
        ("REQMOD GET (clean)", build_reqmod_get_request()),
        ("REQMOD GET (blocked domain)", build_blocked_domain_reqmod()),
        ("REQMOD POST", build_reqmod_post_request()),
        ("RESPMOD (clean)", build_respmod_request()),
        ("RESPMOD (malware keyword)", build_respmod_request(include_malware=True)),
    ]

    failures = 0
    for label, payload in tests:
        try:
            response = send_icap_request(host, port, payload)
            print_response(label, response)
            status_line = response.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
            if "ICAP/1.0" not in status_line:
                print(f"FAIL: unexpected status line: {status_line}")
                failures += 1
        except OSError as exc:
            print(f"\nFAIL {label}: {exc}")
            failures += 1
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ICAP test client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1344)
    parser.add_argument(
        "--test",
        choices=["all", "options", "reqmod", "reqmod-block", "reqmod-post", "respmod", "respmod-block"],
        default="all",
    )
    args = parser.parse_args(argv)

    payloads = {
        "options": ("OPTIONS", build_options_request()),
        "reqmod": ("REQMOD GET", build_reqmod_get_request()),
        "reqmod-block": ("REQMOD blocked domain", build_blocked_domain_reqmod()),
        "reqmod-post": ("REQMOD POST", build_reqmod_post_request()),
        "respmod": ("RESPMOD clean", build_respmod_request()),
        "respmod-block": ("RESPMOD malware", build_respmod_request(include_malware=True)),
    }

    if args.test == "all":
        failures = run_all_tests(args.host, args.port)
        return 1 if failures else 0

    label, payload = payloads[args.test]
    response = send_icap_request(args.host, args.port, payload)
    print_response(label, response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
