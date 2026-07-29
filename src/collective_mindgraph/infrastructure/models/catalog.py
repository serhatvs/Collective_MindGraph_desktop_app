"""Signed model catalogue parsing and verification.

The catalogue is signed with Ed25519 and verified against a key the
installation ships. An unsigned catalogue, a catalogue signed by an unknown
key, and a catalogue whose bytes changed after signing are all rejected the
same way: the product does not fetch model bytes on someone else's say-so.
"""

from __future__ import annotations

import json
from base64 import b64decode
from collections.abc import Mapping
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from collective_mindgraph.domain.model_catalog import ModelEntry, ModelVerificationError

CATALOG_FORMAT = "collective_mindgraph_model_catalog"
CATALOG_FORMAT_VERSION = 1


@dataclass(frozen=True, slots=True)
class SignedCatalog:
    """A verified catalogue and the entries it declares."""

    entries: tuple[ModelEntry, ...]
    issued_at: str

    def entry(self, model_id: str, version: str) -> ModelEntry | None:
        for candidate in self.entries:
            if candidate.key == (model_id, version):
                return candidate
        return None

    def for_engine(self, engine_version: str) -> tuple[ModelEntry, ...]:
        """Return only the entries this engine version may run."""

        return tuple(entry for entry in self.entries if entry.supports_engine(engine_version))


def canonical_payload(document: Mapping[str, object]) -> bytes:
    """Return the exact bytes that are signed.

    Signing a canonical encoding rather than the file as received means a
    reformatted or reordered catalogue still verifies, while any change to a
    field does not.
    """

    body = {key: value for key, value in document.items() if key != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_catalog(raw: str | bytes, *, public_key: bytes) -> SignedCatalog:
    """Verify a catalogue's signature and parse its entries."""

    try:
        document = json.loads(raw)
    except ValueError as error:
        raise ModelVerificationError("The catalogue is not valid JSON.") from error
    if not isinstance(document, dict):
        raise ModelVerificationError("The catalogue must be a JSON object.")
    if (
        document.get("format") != CATALOG_FORMAT
        or document.get("format_version") != CATALOG_FORMAT_VERSION
    ):
        raise ModelVerificationError("Unsupported catalogue format.")

    signature = document.get("signature")
    if not isinstance(signature, str) or not signature:
        raise ModelVerificationError("The catalogue is not signed.")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            b64decode(signature, validate=True),
            canonical_payload(document),
        )
    except (InvalidSignature, ValueError) as error:
        raise ModelVerificationError("The catalogue signature is not valid.") from error

    raw_entries = document.get("models")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ModelVerificationError("The catalogue declares no models.")
    entries: list[ModelEntry] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            raise ModelVerificationError("Every catalogue entry must be an object.")
        try:
            entries.append(
                ModelEntry(
                    model_id=str(item["model_id"]),
                    version=str(item["version"]),
                    provider=str(item["provider"]),
                    size_bytes=int(item["size_bytes"]),
                    license=str(item["license"]),
                    url=str(item["url"]),
                    sha256=str(item["sha256"]).lower(),
                    min_engine=str(item["min_engine"]),
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ModelVerificationError(f"Unusable catalogue entry: {error}") from error

    if len({entry.key for entry in entries}) != len(entries):
        raise ModelVerificationError("The catalogue repeats a model version.")
    return SignedCatalog(entries=tuple(entries), issued_at=str(document.get("issued_at", "")))


__all__ = [
    "CATALOG_FORMAT",
    "CATALOG_FORMAT_VERSION",
    "SignedCatalog",
    "canonical_payload",
    "load_catalog",
]
