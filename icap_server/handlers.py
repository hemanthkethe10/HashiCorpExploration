"""ICAP method handlers (OPTIONS, REQMOD, RESPMOD)."""

from __future__ import annotations

import logging

from .builder import (
    build_100_continue,
    build_204_response,
    build_options_response,
    build_reqmod_modified_response,
    build_respmod_block_page,
    build_respmod_modified_response,
)
from .config import IcapServerConfig
from .constants import METHOD_OPTIONS, METHOD_REQMOD, METHOD_RESPMOD
from .models import IcapRequest
from .policies import ContentPolicy, PolicyResult

logger = logging.getLogger(__name__)


class IcapHandler:
    """Routes ICAP requests to method-specific handlers."""

    def __init__(self, config: IcapServerConfig):
        self.config = config
        self.policy = ContentPolicy(config)

    def handle(self, request: IcapRequest) -> bytes:
        if self.config.log_requests:
            logger.info(
                "ICAP %s %s preview=%s allow_204=%s",
                request.method,
                request.uri,
                request.preview_size(),
                request.allows_204(),
            )

        if request.method == METHOD_OPTIONS:
            return self._handle_options(request)
        if request.method == METHOD_REQMOD:
            return self._handle_reqmod(request)
        if request.method == METHOD_RESPMOD:
            return self._handle_respmod(request)

        return self._error_response(501, "Not Implemented")

    def _handle_options(self, request: IcapRequest) -> bytes:
        service_path = request.uri.rstrip("/").split("/")[-1] or "all"
        methods = ["REQMOD", "RESPMOD"]
        if service_path == "reqmod":
            methods = ["REQMOD"]
        elif service_path == "respmod":
            methods = ["RESPMOD"]

        return build_options_response(
            service_name=self.config.service_name,
            service_id=self.config.service_id,
            istag=self.config.istag,
            methods=methods,
            options_ttl=self.config.options_ttl,
            max_connections=self.config.max_connections,
            preview_size=self.config.preview_size,
        )

    def _handle_reqmod(self, request: IcapRequest) -> bytes:
        preview_result = self._handle_preview(request)
        if preview_result is not None:
            return preview_result

        result = self.policy.evaluate_reqmod(request)
        return self._finalize_reqmod(request, result)

    def _handle_respmod(self, request: IcapRequest) -> bytes:
        preview_result = self._handle_preview(request)
        if preview_result is not None:
            return preview_result

        result = self.policy.evaluate_respmod(request)
        return self._finalize_respmod(request, result)

    def _handle_preview(self, request: IcapRequest) -> bytes | None:
        preview = request.preview_size()
        if preview is None:
            return None

        if request.content.has_ieof:
            return None

        # Demo server always has enough preview data in test scenarios.
        # Real servers would inspect partial body and return 100 Continue.
        return None

    def _finalize_reqmod(self, request: IcapRequest, result: PolicyResult) -> bytes:
        if not result.modified:
            if request.allows_204():
                return build_204_response(self.config.istag)
            return build_204_response(self.config.istag)

        if result.action == "block" and result.request:
            return build_reqmod_modified_response(result.request, self.config.istag)

        if result.request:
            return build_reqmod_modified_response(result.request, self.config.istag)

        return build_204_response(self.config.istag)

    def _finalize_respmod(self, request: IcapRequest, result: PolicyResult) -> bytes:
        if not result.modified:
            if request.allows_204():
                return build_204_response(self.config.istag)
            return build_204_response(self.config.istag)

        if result.action == "block":
            return build_respmod_block_page(
                request.content.response,
                self.config.istag,
                result.block_reason,
            )

        if result.response:
            return build_respmod_modified_response(result.response, self.config.istag)

        return build_204_response(self.config.istag)

    def request_more_preview_data(self, request: IcapRequest) -> bytes:
        """Return 100 Continue when more preview bytes are needed."""
        return build_100_continue(self.config.istag)

    def _error_response(self, code: int, reason: str) -> bytes:
        from .builder import _build_response

        return _build_response(
            code,
            reason,
            {
                "ISTag": f'"{self.config.istag}"',
                "Encapsulated": "null-body=0",
            },
            b"",
        )
