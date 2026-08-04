"""Server configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class IcapServerConfig:
    host: str = "127.0.0.1"
    port: int = 1344
    service_name: str = "HashiCorp ICAP Demo"
    service_id: str = "icap-demo"
    istag: str = "icap-demo-v1"
    options_ttl: int = 3600
    max_connections: int = 100
    preview_size: int = 4096
    blocked_domains: list[str] = field(
        default_factory=lambda: ["malware.example", "blocked.test"]
    )
    blocked_keywords: list[str] = field(
        default_factory=lambda: ["MALWARE_SIGNATURE", "EICAR-STANDARD-ANTIVIRUS-TEST"]
    )
    log_requests: bool = True

    @classmethod
    def from_env(cls) -> IcapServerConfig:
        blocked_domains = os.getenv("ICAP_BLOCKED_DOMAINS", "malware.example,blocked.test")
        blocked_keywords = os.getenv(
            "ICAP_BLOCKED_KEYWORDS",
            "MALWARE_SIGNATURE,EICAR-STANDARD-ANTIVIRUS-TEST",
        )
        return cls(
            host=os.getenv("ICAP_HOST", "127.0.0.1"),
            port=int(os.getenv("ICAP_PORT", "1344")),
            service_name=os.getenv("ICAP_SERVICE_NAME", "HashiCorp ICAP Demo"),
            service_id=os.getenv("ICAP_SERVICE_ID", "icap-demo"),
            istag=os.getenv("ICAP_ISTAG", "icap-demo-v1"),
            options_ttl=int(os.getenv("ICAP_OPTIONS_TTL", "3600")),
            max_connections=int(os.getenv("ICAP_MAX_CONNECTIONS", "100")),
            preview_size=int(os.getenv("ICAP_PREVIEW_SIZE", "4096")),
            blocked_domains=[d.strip() for d in blocked_domains.split(",") if d.strip()],
            blocked_keywords=[k.strip() for k in blocked_keywords.split(",") if k.strip()],
            log_requests=os.getenv("ICAP_LOG_REQUESTS", "true").lower() != "false",
        )
