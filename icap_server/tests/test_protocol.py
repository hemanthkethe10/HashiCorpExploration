"""Unit tests for ICAP protocol helpers."""

import unittest

from icap_server.builder import build_204_response, build_options_response
from icap_server.chunking import decode_chunked_body, encode_chunked_body
from icap_server.client import (
    build_options_request,
    build_reqmod_get_request,
    build_respmod_request,
)
from icap_server.config import IcapServerConfig
from icap_server.handlers import IcapHandler
from icap_server.parser import parse_icap_request
from icap_server.policies import ContentPolicy


class ParserTests(unittest.TestCase):
    def test_parse_options_request(self):
        raw = build_options_request()
        request = parse_icap_request(raw)
        self.assertEqual(request.method, "OPTIONS")
        self.assertIn("encapsulated", request.headers)

    def test_parse_reqmod_get(self):
        raw = build_reqmod_get_request()
        request = parse_icap_request(raw)
        self.assertEqual(request.method, "REQMOD")
        self.assertIsNotNone(request.content.request)
        self.assertEqual(request.content.request.method, "GET")

    def test_parse_respmod(self):
        raw = build_respmod_request()
        request = parse_icap_request(raw)
        self.assertEqual(request.method, "RESPMOD")
        self.assertIsNotNone(request.content.request)
        self.assertIsNotNone(request.content.response)
        self.assertIn(b"Hello ICAP", request.content.response.body)


class BuilderTests(unittest.TestCase):
    def test_build_204_contains_istag(self):
        response = build_204_response("test-tag")
        self.assertIn(b"204 No modifications needed", response)
        self.assertIn(b'ISTag: "test-tag"', response)

    def test_build_options(self):
        response = build_options_response(
            service_name="Test",
            service_id="test",
            istag="v1",
            methods=["REQMOD", "RESPMOD"],
            options_ttl=3600,
            max_connections=10,
            preview_size=4096,
        )
        self.assertIn(b"Methods: REQMOD, RESPMOD", response)
        self.assertIn(b"Preview: 4096", response)


class ChunkingTests(unittest.TestCase):
    def test_roundtrip(self):
        body = b"hello world"
        encoded = encode_chunked_body(body)
        decoded, has_ieof = decode_chunked_body(encoded)
        self.assertEqual(decoded, body)
        self.assertFalse(has_ieof)

    def test_ieof(self):
        encoded = encode_chunked_body(b"partial", ieof=True)
        decoded, has_ieof = decode_chunked_body(encoded)
        self.assertEqual(decoded, b"partial")
        self.assertTrue(has_ieof)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.config = IcapServerConfig()
        self.policy = ContentPolicy(self.config)

    def test_block_domain(self):
        raw = build_reqmod_get_request("http://malware.example/payload")
        request = parse_icap_request(raw)
        result = self.policy.evaluate_reqmod(request)
        self.assertTrue(result.modified)
        self.assertEqual(result.action, "block")

    def test_respmod_blocks_keyword(self):
        raw = build_respmod_request(include_malware=True)
        request = parse_icap_request(raw)
        result = self.policy.evaluate_respmod(request)
        self.assertTrue(result.modified)
        self.assertEqual(result.action, "block")


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.handler = IcapHandler(IcapServerConfig())

    def test_options_handler(self):
        raw = build_options_request()
        request = parse_icap_request(raw)
        response = self.handler.handle(request)
        self.assertIn(b"ICAP/1.0 200 OK", response)

    def test_reqmod_clean_adds_scan_header(self):
        raw = build_reqmod_get_request()
        request = parse_icap_request(raw)
        response = self.handler.handle(request)
        self.assertIn(b"ICAP/1.0 200 OK", response)
        self.assertIn(b"X-Icap-Scanned", response)


if __name__ == "__main__":
    unittest.main()
