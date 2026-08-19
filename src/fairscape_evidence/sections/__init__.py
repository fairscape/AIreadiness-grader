"""Criterion registry: every rubric criterion mapped to its
extract / transform / present trio. Order matches the rubric document."""

from dataclasses import dataclass

from . import (
    characterization,
    computability,
    ethics,
    explainability,
    fairness,
    provenance,
    sustainability,
)


@dataclass
class Criterion:
    id: str
    extract: callable
    transform: callable
    present: callable

    def run(self, ctx):
        raw = self.extract(ctx)
        facts = self.transform(ctx, raw)
        return self.present(facts)


def _trio(module, suffix):
    cid = f"{suffix[0]}.{suffix[1:]}"
    return Criterion(
        id=cid,
        extract=getattr(module, f"extract_{suffix}"),
        transform=getattr(module, f"transform_{suffix}"),
        present=getattr(module, f"present_{suffix}"),
    )


CRITERIA = [
    _trio(fairness, "0a"), _trio(fairness, "0b"),
    _trio(fairness, "0c"), _trio(fairness, "0d"),
    _trio(provenance, "1a"), _trio(provenance, "1b"),
    _trio(provenance, "1c"), _trio(provenance, "1d"),
    _trio(characterization, "2a"), _trio(characterization, "2b"),
    _trio(characterization, "2c"), _trio(characterization, "2d"),
    _trio(characterization, "2e"),
    _trio(explainability, "3a"), _trio(explainability, "3b"),
    _trio(explainability, "3c"),
    _trio(ethics, "4a"), _trio(ethics, "4b"),
    _trio(ethics, "4c"), _trio(ethics, "4d"),
    _trio(sustainability, "5a"), _trio(sustainability, "5b"),
    _trio(sustainability, "5c"), _trio(sustainability, "5d"),
    _trio(computability, "6a"), _trio(computability, "6b"),
    _trio(computability, "6c"), _trio(computability, "6d"),
]
