"""Signed model catalogue and consent-gated installation."""

from .catalog import SignedCatalog, load_catalog
from .installer import ModelConsent, ModelInstaller

__all__ = ["ModelConsent", "ModelInstaller", "SignedCatalog", "load_catalog"]
