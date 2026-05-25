"""Architecture manifests generated from the product spreadsheet."""

from .contracts import DependencyRule, DomainContract, SubmoduleContract
from .registry import DOMAIN_CONTRACTS, SPREADSHEET_SECTIONS

__all__ = [
    "DOMAIN_CONTRACTS",
    "SPREADSHEET_SECTIONS",
    "DependencyRule",
    "DomainContract",
    "SubmoduleContract",
]
