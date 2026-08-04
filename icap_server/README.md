# ICAP Server

RFC 3507 **Internet Content Adaptation Protocol (ICAP)** demo server for learning how ICAP works and testing locally.

## What is ICAP?

ICAP is a lightweight protocol that lets an HTTP proxy **offload content inspection and modification** to a dedicated server. Instead of embedding antivirus, DLP, or filtering logic inside the proxy, the proxy forwards HTTP messages to an ICAP server and applies whatever changes come back.

```
  Client          Proxy (ICAP client)          ICAP Server (this project)
    |                    |                              |
    |---- HTTP request ->|                              |
    |                    |--- REQMOD (encapsulated) --->|
    |                    |<-- 204 or modified request --|
    |                    |---- forwards to origin ----->|
    |                    |<---- HTTP response ----------|
    |                    |--- RESPMOD (encapsulated) -->|
    |                    |<-- 204 or modified response -|
    |<--- HTTP response -|                              |
```

### Common use-cases

| Use-case | ICAP method | What happens |
|----------|-------------|--------------|
| **URL / domain blocking** | REQMOD | Block or rewrite outbound requests before they reach the internet |
| **Antivirus / malware scanning** | RESPMOD | Scan response bodies for signatures |
| **DLP (Data Loss Prevention)** | REQMOD / RESPMOD | Detect sensitive data in uploads or downloads |
| **Content filtering** | RESPMOD | Replace or block HTML containing policy violations |
| **Header injection / logging** | REQMOD | Add `X-Forwarded-*`, tracing, or audit headers |
| **Ad blocking / URL categorization** | RESPMOD | Strip or replace ad payloads in HTML |

### ICAP methods

| Method | Purpose |
|--------|---------|
| `OPTIONS` | Discover server capabilities (supported methods, preview size, ISTag) |
| `REQMOD` | Adapt an HTTP **request** before it is sent upstream |
| `RESPMOD` | Adapt an HTTP **response** before it is returned to the client |

### Key response codes

| Code | Meaning |
|------|---------|
| `100 Continue` | Send more preview bytes (used with `Preview:` header) |
| `200 OK` | Content was modified; encapsulated HTTP is in the body |
| `204 No modifications needed` | Pass-through; proxy uses original HTTP message |

## Project layout

```
icap_server/
  constants.py      # Protocol constants
  models.py         # IcapRequest, HttpMessage, etc.
  parser.py         # Parse ICAP messages and encapsulated HTTP
  builder.py        # Build ICAP responses with Encapsulated offsets
  chunking.py       # Chunked encoding + ieof support
  http_utils.py     # HTTP header helpers
  policies.py       # Demo adaptation policies
  handlers.py       # OPTIONS / REQMOD / RESPMOD handlers
  server.py         # Async TCP server
  client.py         # Local test client
  main.py           # Server entry point
  tests/
```

## Quick start

### 1. Start the server

From the repository root:

```bash
python -m icap_server.main
```

Custom host/port:

```bash
python -m icap_server.main --host 0.0.0.0 --port 1344 --log-level DEBUG
```

The server listens on **TCP port 1344** by default (standard ICAP port).

### 2. Run the test client

In a second terminal:

```bash
# Run all demo scenarios
python -m icap_server.client --test all

# Individual tests
python -m icap_server.client --test options
python -m icap_server.client --test reqmod
python -m icap_server.client --test reqmod-block
python -m icap_server.client --test respmod
python -m icap_server.client --test respmod-block
```

### 3. Run unit tests

```bash
python -m unittest discover -s icap_server/tests -v
```

## Manual testing with netcat

**OPTIONS request:**

```bash
printf 'OPTIONS icap://127.0.0.1:1344/all ICAP/1.0\r\nHost: 127.0.0.1\r\nEncapsulated: null-body=0\r\n\r\n' | nc 127.0.0.1 1344
```

Expected: `ICAP/1.0 200 OK` with `Methods: REQMOD, RESPMOD` and `Preview: 4096`.

## Demo policies

This server implements three teaching policies:

1. **REQMOD domain block** — requests to `malware.example` or `blocked.test` are rewritten to a deny URI
2. **REQMOD header injection** — adds `X-ICAP-Scanned` to requests that lack it
3. **RESPMOD keyword block** — responses containing `MALWARE_SIGNATURE` or `EICAR-STANDARD-ANTIVIRUS-TEST` are replaced with a 403 HTML block page
4. **RESPMOD HTML tag** — appends `<!-- Scanned by ICAP Demo Server -->` to HTML responses

## Configuration (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `ICAP_HOST` | `127.0.0.1` | Bind address |
| `ICAP_PORT` | `1344` | Bind port |
| `ICAP_SERVICE_NAME` | `HashiCorp ICAP Demo` | Service description |
| `ICAP_ISTAG` | `icap-demo-v1` | Service tag (cache invalidation) |
| `ICAP_PREVIEW_SIZE` | `4096` | Advertised preview size |
| `ICAP_BLOCKED_DOMAINS` | `malware.example,blocked.test` | Comma-separated blocked domains |
| `ICAP_BLOCKED_KEYWORDS` | `MALWARE_SIGNATURE,EICAR-...` | Comma-separated response keywords |

Example:

```bash
export ICAP_BLOCKED_DOMAINS="evil.com,bad.net"
export ICAP_PORT=1344
python -m icap_server.main
```

## Integrating with a real proxy

Production proxies (Squid, Blue Coat, Cisco WSA, etc.) act as **ICAP clients**. Point them at:

- **REQMOD service:** `icap://127.0.0.1:1344/reqmod`
- **RESPMOD service:** `icap://127.0.0.1:1344/respmod`

Squid example (`squid.conf` snippet):

```
icap_enable on
icap_send_client_ip on
icap_service service_req reqmod_precache icap://127.0.0.1:1344/reqmod
icap_service service_resp respmod_precache icap://127.0.0.1:1344/respmod
adaptation_access service_req allow all
adaptation_access service_resp allow all
```

## Standards reference

- [RFC 3507 — Internet Content Adaptation Protocol (ICAP)](https://www.rfc-editor.org/rfc/rfc3507)

## Helper API overview

| Module | Key functions |
|--------|---------------|
| `parser.py` | `parse_icap_request()`, `parse_encapsulated_header()`, `extract_encapsulated_content()` |
| `builder.py` | `build_options_response()`, `build_204_response()`, `build_reqmod_modified_response()` |
| `chunking.py` | `encode_chunked_body()`, `decode_chunked_body()` |
| `http_utils.py` | `parse_http_message()`, `serialize_http_message()`, `host_in_message()` |
| `policies.py` | `ContentPolicy.evaluate_reqmod()`, `ContentPolicy.evaluate_respmod()` |
| `handlers.py` | `IcapHandler.handle()` |
