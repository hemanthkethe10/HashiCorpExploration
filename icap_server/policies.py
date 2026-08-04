"""Demo content adaptation policies for learning ICAP use-cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import IcapServerConfig
from .http_utils import host_in_message, set_header
from .models import HttpMessage, IcapRequest


@dataclass
class PolicyResult:
    """Outcome of applying a content policy."""

    modified: bool = False
    allow_204: bool = True
    request: Optional[HttpMessage] = None
    response: Optional[HttpMessage] = None
    block_reason: str = ""
    action: str = "pass"  # pass | block | modify


class ContentPolicy:
    """
    Demonstrates common ICAP adaptation scenarios:

    - URL/domain blocking (REQMOD) — used by proxies to stop outbound requests
    - Malware/DLP keyword scanning (RESPMOD) — inspect response bodies
    - Header injection (REQMOD) — add tracing or security headers
    """

    def __init__(self, config: IcapServerConfig):
        self.config = config

    def evaluate_reqmod(self, request: IcapRequest) -> PolicyResult:
        http_request = request.content.request
        if http_request is None:
            return PolicyResult()

        host = host_in_message(http_request)
        for domain in self.config.blocked_domains:
            if domain in host or domain in http_request.uri.lower():
                return PolicyResult(
                    modified=True,
                    allow_204=False,
                    block_reason=f"Request to blocked domain: {domain}",
                    action="block",
                    request=self._build_blocked_request(http_request, domain),
                )

        if not http_request.has_header("x-icap-scanned"):
            modified_request = set_header(
                http_request, "X-ICAP-Scanned", self.config.service_id
            )
            return PolicyResult(
                modified=True,
                allow_204=False,
                request=modified_request,
                action="modify",
            )

        return PolicyResult(action="pass")

    def evaluate_respmod(self, request: IcapRequest) -> PolicyResult:
        http_response = request.content.response
        if http_response is None:
            return PolicyResult()

        body_text = http_response.body.decode("utf-8", errors="replace")
        for keyword in self.config.blocked_keywords:
            if keyword.lower() in body_text.lower():
                return PolicyResult(
                    modified=True,
                    allow_204=False,
                    block_reason=f"Blocked keyword detected: {keyword}",
                    action="block",
                )

        content_type = http_response.get_header("content-type", "")
        if "text/html" in content_type and b"ICAP Demo" not in http_response.body:
            modified_body = http_response.body + b"\n<!-- Scanned by ICAP Demo Server -->"
            modified_response = HttpMessage(
                start_line=http_response.start_line,
                headers=dict(http_response.headers),
                body=modified_body,
            )
            return PolicyResult(
                modified=True,
                allow_204=False,
                response=modified_response,
                action="modify",
            )

        return PolicyResult(action="pass")

    def _build_blocked_request(self, request: HttpMessage, domain: str) -> HttpMessage:
        """Redirect blocked request to a local deny URI (demo only)."""
        blocked_line = f"GET http://icap-blocked.local/denied?domain={domain} HTTP/1.1"
        return HttpMessage(
            start_line=blocked_line,
            headers={
                "host": "icap-blocked.local",
                "connection": "close",
                "x-icap-blocked": "true",
                "x-icap-block-reason": f"domain:{domain}",
            },
            body=b"",
        )
