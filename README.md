# Sample Server - Vault OIDC Integration

A FastAPI server implementing Vault OIDC Provider authentication flow.

## Project Structure

```
sample_server/
├── config.py                    # Configuration and token storage
├── main.py                      # Core OIDC endpoints (production-ready)
├── diagnostics.py              # Helper endpoints for debugging
├── main_with_diagnostics.py    # Main app with diagnostics included
├── requirements.txt
└── README.md
```

## Core OIDC Endpoints (main.py)

### Authentication Flow
1. **GET /health** - Health check
2. **GET /auth/login** - Initiate OIDC flow, returns authorization URL
3. **GET /auth/callback** - OIDC redirect callback, exchanges code for tokens
4. **GET /auth/tokens** - View stored token info (masked by default)
5. **GET /auth/tokens/decode-id-token** - Decode JWT ID token claims
6. **DELETE /auth/tokens** - Clear stored tokens

### Vault Secret Operations
7. **GET /vault/secrets/{path}** - Read a secret from Vault
8. **POST /vault/secrets/{path}** - Write a secret to Vault
9. **GET /vault/secrets** - List secrets at a path

## Diagnostic Endpoints (diagnostics.py)

Optional endpoints for debugging and configuration verification:

1. **GET /auth/discovery** - Fetch OIDC discovery configuration
2. **GET /auth/verify-config** - Verify client configuration in Vault
3. **GET /auth/check-provider** - Check provider configuration
4. **GET /auth/vault/secret-engines** - Test Vault API access

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure Vault OIDC settings in `config.py`:
   - VAULT_ADDR
   - CLIENT_ID
   - CLIENT_SECRET
   - REDIRECT_URI

3. Run the server:

**Production (core endpoints only):**
```bash
uvicorn main:app --reload --port 8000
```

**Development (with diagnostics):**
```bash
uvicorn main_with_diagnostics:app --reload --port 8000
```

## OIDC Flow

1. Visit `http://localhost:8000/auth/login`
2. Copy the authorization URL from the response
3. Open the URL in your browser
4. Authenticate with Vault (you'll be prompted if not logged in)
5. You'll be redirected to `/auth/callback` which will:
   - Exchange the authorization code for tokens
   - Store tokens in memory
   - Fetch and display userinfo

## View Stored Tokens

```bash
# View tokens (masked)
curl http://localhost:8000/auth/tokens

# View tokens (full values)
curl http://localhost:8000/auth/tokens?show_secrets=true

# Decode ID token to see claims
curl http://localhost:8000/auth/tokens/decode-id-token

# Clear tokens
curl -X DELETE http://localhost:8000/auth/tokens
```

## Working with Vault Secrets

**Important:** The OIDC access token only has permission to access the userinfo endpoint. To read/write secrets, you need a proper Vault token.

### Get a Vault Token

```bash
# Login to Vault
vault login

# Or use an auth method
vault login -method=userpass username=myuser
```

### Read a Secret

```bash
# Read a secret (KV v2)
curl "http://localhost:8000/vault/secrets/secret/data/myapp/config?vault_token=YOUR_VAULT_TOKEN"

# Try with OIDC token (will likely fail with permission denied)
curl "http://localhost:8000/vault/secrets/secret/data/myapp/config?use_oidc_token=true"
```

### Write a Secret

```bash
# Write a secret (KV v2)
curl -X POST "http://localhost:8000/vault/secrets/secret/data/myapp/config?vault_token=YOUR_VAULT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data": {"username": "admin", "password": "secret123"}}'
```

### List Secrets

```bash
# List secrets at a path
curl "http://localhost:8000/vault/secrets?path=secret/metadata/myapp&vault_token=YOUR_VAULT_TOKEN"

# List all secrets in default path
curl "http://localhost:8000/vault/secrets?vault_token=YOUR_VAULT_TOKEN"
```

## Important Notes

- Tokens are stored in memory and will be lost on server restart
- The OIDC access token is a Vault batch token that only provides access to the userinfo endpoint
- To access other Vault APIs, you need a separate Vault token (not the OIDC access token)
- Client authentication uses the `client_secret_basic` method

## Configuration

All configuration is in `config.py`. Update these values to match your Vault setup:

```python
VAULT_ADDR = "http://127.0.0.1:8200"
VAULT_NAMESPACE = ""  # For Vault Enterprise
PROVIDER_NAME = "default"
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"
REDIRECT_URI = "your_redirect_uri"
```

## Troubleshooting

If you get "Invalid client ID" error:

1. Ensure the provider allows your client:
```bash
vault write identity/oidc/provider/default allowed_client_ids="*"
```

2. Verify redirect URI matches exactly:
```bash
vault read identity/oidc/client/your-client-name
```

For more debugging, use the diagnostic endpoints in `main_with_diagnostics.py`.

