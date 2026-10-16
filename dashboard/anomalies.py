"""Modèle d'une anomalie détectée pendant le chargement ou la validation."""

from dataclasses import asdict, dataclass

ERROR = "erreur"  # ligne (ou fichier) exclue des calculs
WARNING = "avertissement"  # ligne conservée mais signalée


@dataclass(frozen=True)
class Anomaly:
    severity: str
    rule: str
    message: str
    file: str
    line: int | None = None  # numéro de ligne physique dans le CSV (en-tête = 1)
    sku: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
