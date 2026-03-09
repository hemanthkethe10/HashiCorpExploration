# TLS and mTLS Configuration Guide

## Overview

This document explains how TLS (server authentication) and mTLS (mutual authentication) work with Caddy and client tools like curl.

---

## 1. Server TLS (One-Way Authentication)

**Goal:** Client verifies the server's identity

### Server Side (Caddy)

**What Caddy needs:**
- `server-fullchain.pem` - Server certificate + intermediate CA(s)
- `server-key.pem` - Server's private key

```caddyfile
gateway.local {
    tls ./certs/echo-fullchain.pem ./certs/echo-key.pem
    reverse_proxy 127.0.0.1:8000
}
```

**Why fullchain?**
- Client needs to verify the certificate chain
- Server must send: [Server Cert] → [Intermediate CA] → [Root CA]
- If any link is missing, client can't verify and rejects the connection

### Client Side (curl)

**What client needs:**
- `issuing_ca.pem` - Root or intermediate CA that signed the server cert

```bash
curl --cacert certs/issuing_ca.pem https://gateway.local/health
```

**Flow:**
1. Client connects to server
2. Server sends its fullchain certificate
3. Client verifies: "Is this cert signed by a CA I trust?"
4. Client checks `issuing_ca.pem` to validate the signature
5. Connection established ✓

---

## 2. Mutual TLS (Two-Way Authentication)

**Goal:** Both client AND server verify each other's identity

### Server Side (Caddy)

**What Caddy needs:**
- `server-fullchain.pem` - Server certificate + intermediate CA(s)
- `server-key.pem` - Server's private key
- `issuing_ca.pem` - CA that must have signed client certificates

```caddyfile
gateway.local {
    tls ./certs/echo-fullchain.pem ./certs/echo-key.pem {
        client_auth {
            mode require_and_verify
            trusted_ca_cert_file ./certs/issuing_ca.pem
        }
    }
    reverse_proxy 127.0.0.1:8000
}
```

**Client authentication modes:**
- `request` - Ask for cert but allow connections without it
- `require` - Require cert but don't verify signature (insecure)
- `require_and_verify` - Require cert AND verify it's signed by trusted CA ✓

### Client Side (curl)

**What client needs:**
- `issuing_ca.pem` - CA to verify server's certificate
- `client-cert.pem` or `client-fullchain.pem` - Client's certificate
- `client-key.pem` - Client's private key

```bash
curl --cacert certs/issuing_ca.pem \
     --cert client-cert.pem \
     --key client-key.pem \
     https://gateway.local/health
```

**When to use client fullchain:**
- If client cert is signed by intermediate CA → Use fullchain
- If client cert is signed directly by root CA → Either works

**Flow:**
1. Client connects to server
2. Server sends its fullchain certificate
3. Client verifies server cert using `issuing_ca.pem`
4. Server requests client certificate
5. Client sends its certificate (+ chain if needed)
6. Server verifies client cert using `trusted_ca_cert_file`
7. Both parties authenticated ✓

---

## Summary Table

| Component | Server TLS | mTLS (Server) | mTLS (Client) |
|-----------|------------|---------------|---------------|
| Server cert fullchain | ✓ Required | ✓ Required | N/A |
| Server private key | ✓ Required | ✓ Required | N/A |
| Server trusted CA | ✗ Not needed | ✓ Required | N/A |
| Client cert | ✗ Not needed | N/A | ✓ Required |
| Client private key | ✗ Not needed | N/A | ✓ Required |
| Client trusted CA | ✓ Required | N/A | ✓ Required |

---

## Key Concepts

### Why Fullchain?

TLS requires a complete chain of trust:
```
[Your Cert] → [Intermediate CA] → [Root CA]
```

If you only send `[Your Cert]`, the other party can't verify who signed it unless they already have the intermediate CA in their trust store.

### Private Keys

- Always kept separate from certificates
- Never shared or transmitted
- Used to prove you own the certificate
- Server and client each have their own private key

### CA Certificates

- Used to verify signatures
- Can be root CA or intermediate CA
- Must match the CA that signed the certificate being verified
- Shared publicly (not secret like private keys)

---

## Testing

### Test Server TLS Only
```bash
curl --cacert certs/issuing_ca.pem https://gateway.local/health
```

### Test mTLS
```bash
curl --cacert certs/issuing_ca.pem \
     --cert client-cert.pem \
     --key client-key.pem \
     https://gateway.local/health
```

### Test mTLS Failure (no client cert)
```bash
curl --cacert certs/issuing_ca.pem https://gateway.local/health
# Expected: SSL handshake failure
```

---

## Common Issues

1. **"tlsv1 alert internal error"** → Multiple Caddy instances or cert/key mismatch
2. **"certificate verify failed"** → Wrong CA file or incomplete chain
3. **"handshake failure"** → mTLS enabled but no client cert provided
4. **"unknown ca"** → Client cert not signed by trusted CA

---

## File Structure

```
certs/
├── echo-fullchain.pem      # Server cert + intermediate CA
├── echo-key.pem            # Server private key
├── issuing_ca.pem          # Root/Intermediate CA (for verification)
├── client-cert.pem         # Client certificate
└── client-key.pem          # Client private key
```
