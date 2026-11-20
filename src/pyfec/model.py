"""Structures de données du FEC (article A47 A-1 du Livre des procédures fiscales)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

#: Colonnes obligatoires, dans l'ordre imposé par l'article A47 A-1 du LPF.
COLONNES_DEBIT_CREDIT = (
    "JournalCode",
    "JournalLib",
    "EcritureNum",
    "EcritureDate",
    "CompteNum",
    "CompteLib",
    "CompAuxNum",
    "CompAuxLib",
    "PieceRef",
    "PieceDate",
    "EcritureLib",
    "Debit",
    "Credit",
    "EcritureLet",
    "DateLet",
    "ValidDate",
    "Montantdevise",
    "Idevise",
)

#: Variante admise : un montant et un sens (D/C) à la place de Debit/Credit.
COLONNES_MONTANT_SENS = (
    COLONNES_DEBIT_CREDIT[:11]
    + ("Montant", "Sens")
    + COLONNES_DEBIT_CREDIT[13:]
)


class Severite(str, Enum):
    ERREUR = "erreur"
    AVERTISSEMENT = "avertissement"


@dataclass(frozen=True)
class Anomalie:
    """Un problème détecté dans le fichier."""

    code: str
    message: str
    severite: Severite = Severite.ERREUR
    ligne: Optional[int] = None  # numéro de ligne dans le fichier (1 = en-tête)

    def __str__(self) -> str:
        where = f"ligne {self.ligne} : " if self.ligne is not None else ""
        return f"[{self.severite.value}] {self.code} {where}{self.message}"


@dataclass
class LigneEcriture:
    """Une ligne du FEC, avec ses valeurs converties."""

    ligne: int
    journal_code: str
    journal_lib: str
    ecriture_num: str
    ecriture_date: Optional[date]
    compte_num: str
    compte_lib: str
    comp_aux_num: str
    comp_aux_lib: str
    piece_ref: str
    piece_date: Optional[date]
    ecriture_lib: str
    debit: Decimal
    credit: Decimal
    ecriture_let: str
    date_let: Optional[date]
    valid_date: Optional[date]
    montant_devise: Optional[Decimal]
    idevise: str
    brut: dict = field(default_factory=dict, repr=False)

    @property
    def solde(self) -> Decimal:
        return self.debit - self.credit


@dataclass
class FichierFEC:
    """Résultat de la lecture d'un FEC."""

    chemin: str
    encodage: str
    separateur: str
    format: str  # "debit_credit" ou "montant_sens"
    entete: list
    lignes: list = field(default_factory=list)
    anomalies: list = field(default_factory=list)

    @property
    def total_debit(self) -> Decimal:
        return sum((l.debit for l in self.lignes), Decimal("0"))

    @property
    def total_credit(self) -> Decimal:
        return sum((l.credit for l in self.lignes), Decimal("0"))
