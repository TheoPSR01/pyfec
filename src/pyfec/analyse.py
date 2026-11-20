"""Restitutions à partir d'un FEC : balance générale, journaux, export CSV."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional, TextIO

from .model import FichierFEC

ZERO = Decimal("0")


@dataclass
class LigneBalance:
    compte_num: str
    compte_lib: str
    debit: Decimal
    credit: Decimal

    @property
    def solde(self) -> Decimal:
        return self.debit - self.credit

    @property
    def solde_debiteur(self) -> Decimal:
        return self.solde if self.solde > 0 else ZERO

    @property
    def solde_crediteur(self) -> Decimal:
        return -self.solde if self.solde < 0 else ZERO


def balance(fec: FichierFEC, niveau: Optional[int] = None) -> list:
    """Balance générale, triée par numéro de compte.

    ``niveau`` regroupe les comptes sur leurs N premiers caractères
    (``niveau=1`` donne la balance par classe, ``niveau=3`` par compte à 3 chiffres).
    """
    cumul = defaultdict(lambda: [ZERO, ZERO, ""])
    for l in fec.lignes:
        cle = l.compte_num[:niveau] if niveau else l.compte_num
        c = cumul[cle]
        c[0] += l.debit
        c[1] += l.credit
        if not c[2]:
            c[2] = l.compte_lib if not niveau or len(l.compte_num) <= niveau else ""
    return [LigneBalance(k, v[2], v[0], v[1]) for k, v in sorted(cumul.items())]


def totaux_par_journal(fec: FichierFEC) -> list:
    """(code, libellé, nb_écritures, débit, crédit) par journal."""
    data = defaultdict(lambda: ["", set(), ZERO, ZERO])
    for l in fec.lignes:
        d = data[l.journal_code]
        d[0] = d[0] or l.journal_lib
        d[1].add(l.ecriture_num)
        d[2] += l.debit
        d[3] += l.credit
    return [(k, v[0], len(v[1]), v[2], v[3]) for k, v in sorted(data.items())]


def solde_classes(fec: FichierFEC, classes: Iterable[str]) -> Decimal:
    """Somme des soldes (débit - crédit) des comptes commençant par l'un des préfixes."""
    prefixes = tuple(classes)
    return sum((l.solde for l in fec.lignes if l.compte_num.startswith(prefixes)), ZERO)


def resultat(fec: FichierFEC) -> Decimal:
    """Résultat de l'exercice (produits - charges), à partir des classes 6 et 7."""
    return -(solde_classes(fec, ["6"]) + solde_classes(fec, ["7"]))


def ecrire_balance_csv(lignes: list, sortie: TextIO, separateur: str = ";") -> None:
    """Écrit une balance au format CSV (virgule décimale, lisible par Excel en français)."""
    w = csv.writer(sortie, delimiter=separateur)
    w.writerow(["CompteNum", "CompteLib", "Debit", "Credit", "SoldeDebiteur", "SoldeCrediteur"])

    def fmt(x: Decimal) -> str:
        return f"{x:.2f}".replace(".", ",")

    for b in lignes:
        w.writerow([b.compte_num, b.compte_lib, fmt(b.debit), fmt(b.credit),
                    fmt(b.solde_debiteur), fmt(b.solde_crediteur)])
