"""Trusted source registry for Tier 3 legal and SOP ingestion.

Firecrawl is used as a discovery and scrape layer only. This registry decides
whether a crawled URL is eligible to become a corpus candidate; promotion into
Qdrant still requires the citation validator and a legal/SOP owner review.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class SourceTier(str, Enum):
    """Trust tier for a crawled source."""

    OFFICIAL_LEGAL = "official_legal"
    LEGAL_CROSSCHECK = "legal_crosscheck"
    PUBLIC_OPERATIONAL = "public_operational"
    INTERNAL_SOP = "internal_sop"


class DocumentClass(str, Enum):
    """Document class handled by the Firecrawl ingestion gate."""

    STATUTE = "statute"
    DECREE = "decree"
    CIRCULAR = "circular"
    SOP = "sop"
    PUBLIC_CONTEXT = "public_context"


@dataclass(frozen=True)
class TrustedSource:
    """Allowlisted source host and how it may be used."""

    source_id: str
    host: str
    tier: SourceTier
    document_classes: tuple[DocumentClass, ...]
    source_role: str
    owner: str
    can_seed_legal_corpus: bool
    notes: str

    def matches(self, host: str) -> bool:
        """Return True when a URL host matches this source exactly or by subdomain."""
        normalized = host.lower().strip(".")
        registered = self.host.lower().strip(".")
        return normalized == registered or normalized.endswith(f".{registered}")


class SourceRegistryError(ValueError):
    """Raised when a crawled URL is not acceptable for corpus ingestion."""


DEFAULT_TRUSTED_SOURCES: tuple[TrustedSource, ...] = (
    TrustedSource(
        source_id="vn-government-legal-pages",
        host="vanban.chinhphu.vn",
        tier=SourceTier.OFFICIAL_LEGAL,
        document_classes=(DocumentClass.STATUTE, DocumentClass.DECREE, DocumentClass.CIRCULAR),
        source_role="authoritative_content",
        owner="legal_reviewer",
        can_seed_legal_corpus=True,
        notes="Official Government legal document pages; Firecrawl snapshots still need owner review.",
    ),
    TrustedSource(
        source_id="vn-government-legal-files",
        host="datafiles.chinhphu.vn",
        tier=SourceTier.OFFICIAL_LEGAL,
        document_classes=(DocumentClass.STATUTE, DocumentClass.DECREE, DocumentClass.CIRCULAR),
        source_role="authoritative_attachment",
        owner="legal_reviewer",
        can_seed_legal_corpus=True,
        notes="Official PDF attachments linked from vanban.chinhphu.vn.",
    ),
    TrustedSource(
        source_id="vbpl-crosscheck",
        host="vbpl.vn",
        tier=SourceTier.LEGAL_CROSSCHECK,
        document_classes=(DocumentClass.STATUTE, DocumentClass.DECREE, DocumentClass.CIRCULAR),
        source_role="validity_crosscheck_only",
        owner="legal_reviewer",
        can_seed_legal_corpus=False,
        notes="Used to cross-check effective/superseded relationships, not as canonical content.",
    ),
    TrustedSource(
        source_id="hcmc-government-public-operations",
        host="tphcm.chinhphu.vn",
        tier=SourceTier.PUBLIC_OPERATIONAL,
        document_classes=(DocumentClass.PUBLIC_CONTEXT,),
        source_role="public_operational_context",
        owner="ops_reviewer",
        can_seed_legal_corpus=False,
        notes="Public HCMC operational context; not an approved SOP without owner metadata.",
    ),
    TrustedSource(
        source_id="hcmc-transport-department",
        host="sgtvt.hochiminhcity.gov.vn",
        tier=SourceTier.PUBLIC_OPERATIONAL,
        document_classes=(DocumentClass.PUBLIC_CONTEXT, DocumentClass.SOP),
        source_role="candidate_sop_context",
        owner="ops_reviewer",
        can_seed_legal_corpus=False,
        notes="Candidate SOP/public policy source; requires issuing authority, approval date, and scope.",
    ),
    TrustedSource(
        source_id="traffic-police-public-guidance",
        host="csgt.vn",
        tier=SourceTier.PUBLIC_OPERATIONAL,
        document_classes=(DocumentClass.PUBLIC_CONTEXT,),
        source_role="public_operational_context",
        owner="ops_reviewer",
        can_seed_legal_corpus=False,
        notes="Public traffic-safety guidance; not a substitute for approved local SOP.",
    ),
)


def canonical_https_host(url: str) -> str:
    """Validate a source URL and return its canonical host."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SourceRegistryError("source_url must use https")
    if not parsed.hostname:
        raise SourceRegistryError("source_url must include a host")
    return parsed.hostname.lower()


def find_trusted_source(
    url: str,
    registry: tuple[TrustedSource, ...] = DEFAULT_TRUSTED_SOURCES,
) -> TrustedSource | None:
    """Resolve an HTTPS URL to a trusted source policy."""
    host = canonical_https_host(url)
    for source in registry:
        if source.matches(host):
            return source
    return None


def require_trusted_source(
    url: str,
    registry: tuple[TrustedSource, ...] = DEFAULT_TRUSTED_SOURCES,
) -> TrustedSource:
    """Return the source policy or fail closed for untrusted URLs."""
    source = find_trusted_source(url, registry)
    if source is None:
        raise SourceRegistryError(f"source_url is not in the trusted registry: {url}")
    return source


__all__ = [
    "DEFAULT_TRUSTED_SOURCES",
    "DocumentClass",
    "SourceRegistryError",
    "SourceTier",
    "TrustedSource",
    "canonical_https_host",
    "find_trusted_source",
    "require_trusted_source",
]
