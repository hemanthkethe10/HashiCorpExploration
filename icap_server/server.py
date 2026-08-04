"""Async TCP ICAP server."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .config import IcapServerConfig
from .handlers import IcapHandler
from .parser import is_complete_icap_message, parse_icap_request

logger = logging.getLogger(__name__)


class IcapServer:
    """RFC 3507 ICAP server using asyncio."""

    def __init__(self, config: Optional[IcapServerConfig] = None):
        self.config = config or IcapServerConfig.from_env()
        self.handler = IcapHandler(self.config)
        self._server: Optional[asyncio.AbstractServer] = None

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        buffer = b""

        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    break
                buffer += chunk

                if not is_complete_icap_message(buffer):
                    continue

                response = self._process_buffer(buffer)
                writer.write(response)
                await writer.drain()
                break
        except Exception:
            logger.exception("Error handling ICAP client %s", peer)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    def _process_buffer(self, buffer: bytes) -> bytes:
        request = parse_icap_request(buffer)
        return self.handler.handle(request)

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self.handle_client,
            host=self.config.host,
            port=self.config.port,
        )
        addrs = ", ".join(str(sock.getsockname()) for sock in self._server.sockets or [])
        logger.info("ICAP server listening on %s", addrs)
        logger.info("Service: %s (ISTag: %s)", self.config.service_name, self.config.istag)

    async def serve_forever(self) -> None:
        if self._server is None:
            await self.start()
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
