"""Rollout flags with a fixed order and independent rollback.

Each flag can be rolled back on its own, and a flag can only be enabled once
everything it depends on already is. Migration is deliberately absent from this
set: data must upgrade whether or not any feature is switched on, or a rollback
would leave the database ahead of the code that reads it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum


class FeatureFlag(StrEnum):
    """Everything the rollout can switch, in the order it is switched."""

    SCHEMA = "schema"
    CRYPTO = "crypto"
    SYNC = "sync"
    COLLABORATION = "collaboration"
    GRAPH = "graph"
    TELEMETRY = "telemetry"


# The programme fixes this order. Encryption is useless before the identities
# exist, sync cannot carry what is not sealed, collaboration rides on sync, and
# telemetry goes last because it is the only one the user opts into.
ROLLOUT_ORDER: tuple[FeatureFlag, ...] = (
    FeatureFlag.SCHEMA,
    FeatureFlag.CRYPTO,
    FeatureFlag.SYNC,
    FeatureFlag.COLLABORATION,
    FeatureFlag.GRAPH,
    FeatureFlag.TELEMETRY,
)

# The graph canvas is a local view; it needs the schema but not the cloud.
_PREREQUISITES: Mapping[FeatureFlag, tuple[FeatureFlag, ...]] = {
    FeatureFlag.SCHEMA: (),
    FeatureFlag.CRYPTO: (FeatureFlag.SCHEMA,),
    FeatureFlag.SYNC: (FeatureFlag.SCHEMA, FeatureFlag.CRYPTO),
    FeatureFlag.COLLABORATION: (FeatureFlag.SCHEMA, FeatureFlag.CRYPTO, FeatureFlag.SYNC),
    FeatureFlag.GRAPH: (FeatureFlag.SCHEMA,),
    FeatureFlag.TELEMETRY: (),
}


class FlagOrderError(RuntimeError):
    """Raised when enabling a flag would break the declared order."""


@dataclass(frozen=True, slots=True)
class FeatureFlagSet:
    """An immutable set of enabled flags."""

    enabled: frozenset[FeatureFlag] = frozenset()

    @classmethod
    def none(cls) -> FeatureFlagSet:
        return cls()

    def is_enabled(self, flag: FeatureFlag) -> bool:
        return flag in self.enabled

    def missing_prerequisites(self, flag: FeatureFlag) -> tuple[FeatureFlag, ...]:
        return tuple(required for required in _PREREQUISITES[flag] if required not in self.enabled)

    def enable(self, flag: FeatureFlag) -> FeatureFlagSet:
        """Turn one flag on, refusing to skip anything it depends on."""

        missing = self.missing_prerequisites(flag)
        if missing:
            names = ", ".join(entry.value for entry in missing)
            raise FlagOrderError(f"{flag.value} requires {names} to be enabled first.")
        return FeatureFlagSet(enabled=self.enabled | {flag})

    def disable(self, flag: FeatureFlag) -> FeatureFlagSet:
        """Roll one flag back, and everything that depends on it.

        Rolling back a dependency while its dependants stay on would leave the
        product in a state nobody tested, so the dependants come off too.
        """

        removed = {flag} | {
            candidate
            for candidate in FeatureFlag
            if flag in _PREREQUISITES[candidate] and candidate in self.enabled
        }
        return FeatureFlagSet(enabled=self.enabled - removed)

    def enable_through(self, flag: FeatureFlag) -> FeatureFlagSet:
        """Enable every flag up to and including one, in the declared order."""

        current = self
        for candidate in ROLLOUT_ORDER:
            current = current.enable(candidate)
            if candidate is flag:
                break
        return current

    @property
    def rollout_position(self) -> int:
        """How far the rollout has got along the declared order."""

        position = 0
        for index, flag in enumerate(ROLLOUT_ORDER, start=1):
            if flag not in self.enabled:
                break
            position = index
        return position


def parse_flags(values: Iterable[str]) -> FeatureFlagSet:
    """Build a flag set from configuration, validating the order."""

    current = FeatureFlagSet.none()
    wanted = {FeatureFlag(value.strip()) for value in values if value.strip()}
    for flag in ROLLOUT_ORDER:
        if flag in wanted:
            current = current.enable(flag)
    return current


__all__ = [
    "ROLLOUT_ORDER",
    "FeatureFlag",
    "FeatureFlagSet",
    "FlagOrderError",
    "parse_flags",
]
