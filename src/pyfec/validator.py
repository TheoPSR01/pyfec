"""Contrôles de cohérence d'un FEC."""

from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from .model import Anomalie, FichierFEC, Severite

ZERO = Decimal("0")
NOM_FICHIER = re.compile(r"^(?P<siren>\d{9})FEC(?P<cloture>\d{8})", re.IGNORECASE)


@dataclass
class Rapport:
    """Résultat des contrôles."""

    fec: FichierFEC
    anomalies: list = field(default_factory=list)
    siren: Optional[str] = None
    date_cloture: Optional[date] = None

    @property
    def erreurs(self) -> list:
        return [a for a in self.anomalies if a.severite is Severite.ERREUR]

    @property
    def avertissements(self) -> list:
        return [a for a in self.anomalies if a.severite is Severite.AVERTISSEMENT]

    @property
    def est_valide(self) -> bool:
        return not self.erreurs

    @property
    def nb_ecritures(self) -> int:
        return len({(l.journal_code, l.ecriture_num) for l in self.fec.lignes})

    def resume(self) -> str:
        f = self.fec
        lignes = [
            f"Fichier      : {f.chemin}",
            f"Encodage     : {f.encodage}  |  séparateur : {'tabulation' if f.separateur == chr(9) else repr(f.separateur)}  |  format : {f.format}",
        ]
        if self.siren:
            lignes.append(f"SIREN        : {self.siren}  |  clôture : {self.date_cloture}")
        lignes += [
            f"Lignes       : {len(f.lignes)}  |  écritures : {self.nb_ecritures}",
            "Total débit  : " + _fr(f.total_debit),
            "Total crédit : " + _fr(f.total_credit),
            f"Résultat     : {len(self.erreurs)} erreur(s), {len(self.avertissements)} avertissement(s)",
            "",
            "FEC CONFORME aux contrôles effectués" if self.est_valide else "FEC NON CONFORME",
        ]
        return "\n".join(lignes)


def _fr(x: Decimal) -> str:
    return f"{x:,.2f}".replace(",", " ").replace(".", ",")


def _infos_nom_fichier(chemin: str) -> tuple[Optional[str], Optional[date]]:
    m = NOM_FICHIER.match(os.path.basename(chemin))
    if not m:
        return None, None
    c = m.group("cloture")
    try:
        return m.group("siren"), date(int(c[:4]), int(c[4:6]), int(c[6:]))
    except ValueError:
        return m.group("siren"), None


def siren_valide(siren: str) -> bool:
    """Contrôle de Luhn d'un numéro SIREN."""
    if not re.fullmatch(r"\d{9}", siren):
        return False
    total = 0
    for i, ch in enumerate(siren):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def valider(
    fec: FichierFEC,
    debut_exercice: Optional[date] = None,
    fin_exercice: Optional[date] = None,
    tolerance: Decimal = Decimal("0.005"),
) -> Rapport:
    """Exécute l'ensemble des contrôles et renvoie un :class:`Rapport`.

    ``debut_exercice`` et ``fin_exercice`` sont facultatifs. Sans eux, la date
    de clôture est lue dans le nom du fichier (``SIRENFECAAAAMMJJ``) quand il
    respecte la norme, et le contrôle des dates hors exercice porte seulement
    sur la borne de fin.
    """
    rapport = Rapport(fec, anomalies=list(fec.anomalies))
    a = rapport.anomalies.append

    # Nom du fichier
    siren, cloture = _infos_nom_fichier(fec.chemin)
    rapport.siren, rapport.date_cloture = siren, cloture
    if fec.chemin != "<bytes>":
        if siren is None:
            a(Anomalie("V014", "nom de fichier non conforme (attendu SIRENFECAAAAMMJJ)", Severite.AVERTISSEMENT))
        elif not siren_valide(siren):
            a(Anomalie("V015", f"SIREN {siren} invalide (clé de Luhn)", Severite.AVERTISSEMENT))
    fin = fin_exercice or cloture

    if not fec.lignes:
        a(Anomalie("V000", "aucune écriture dans le fichier"))
        return rapport

    ecritures = defaultdict(list)
    numeros_par_journal = defaultdict(set)

    for l in fec.lignes:
        n = l.ligne
        for nom, val in (
            ("JournalCode", l.journal_code), ("JournalLib", l.journal_lib),
            ("EcritureNum", l.ecriture_num), ("CompteNum", l.compte_num),
            ("CompteLib", l.compte_lib), ("PieceRef", l.piece_ref),
            ("EcritureLib", l.ecriture_lib),
        ):
            if not val:
                a(Anomalie("V004", f"{nom} vide", ligne=n))

        if l.compte_num:
            if not l.compte_num[0] in "12345678":
                a(Anomalie("V003", f"CompteNum {l.compte_num!r} ne commence pas par une classe 1 à 8", ligne=n))
            elif len(l.compte_num) < 3:
                a(Anomalie("V003", f"CompteNum {l.compte_num!r} trop court (3 caractères minimum)", ligne=n))

        if l.debit < 0 or l.credit < 0:
            a(Anomalie("V006", "montant négatif", Severite.AVERTISSEMENT, ligne=n))
        if l.debit != 0 and l.credit != 0:
            a(Anomalie("V005", "débit et crédit renseignés sur la même ligne", Severite.AVERTISSEMENT, ligne=n))
        elif l.debit == 0 and l.credit == 0:
            a(Anomalie("V005", "ligne à montant nul", Severite.AVERTISSEMENT, ligne=n))

        if bool(l.comp_aux_num) != bool(l.comp_aux_lib):
            a(Anomalie("V011", "CompAuxNum et CompAuxLib doivent être renseignés ensemble", ligne=n))
        if l.ecriture_let and not l.date_let:
            a(Anomalie("V012", "EcritureLet renseigné sans DateLet", Severite.AVERTISSEMENT, ligne=n))
        if l.montant_devise is not None and l.montant_devise != 0 and not l.idevise:
            a(Anomalie("V013", "Montantdevise renseigné sans Idevise", ligne=n))

        if l.ecriture_date and l.valid_date and l.valid_date < l.ecriture_date:
            a(Anomalie("V007", "ValidDate antérieure à EcritureDate", Severite.AVERTISSEMENT, ligne=n))
        if l.ecriture_date:
            if fin and l.ecriture_date > fin:
                a(Anomalie("V008", f"EcritureDate {l.ecriture_date} après la clôture {fin}", ligne=n))
            if debut_exercice and l.ecriture_date < debut_exercice:
                a(Anomalie("V008", f"EcritureDate {l.ecriture_date} avant l'ouverture {debut_exercice}", ligne=n))

        ecritures[(l.journal_code, l.ecriture_num)].append(l)
        numeros_par_journal[l.journal_code].add(l.ecriture_num)

    # Équilibre de chaque écriture
    for (journal, num), lignes in ecritures.items():
        ecart = sum((x.debit - x.credit for x in lignes), ZERO)
        if abs(ecart) > tolerance:
            a(Anomalie("V001", f"écriture {journal}/{num} déséquilibrée (écart {ecart:.2f})", ligne=lignes[0].ligne))
        dates = {x.ecriture_date for x in lignes if x.ecriture_date}
        if len(dates) > 1:
            a(Anomalie("V010", f"écriture {journal}/{num} porte plusieurs dates d'écriture", ligne=lignes[0].ligne))

    # Équilibre général
    ecart_total = fec.total_debit - fec.total_credit
    if abs(ecart_total) > tolerance:
        a(Anomalie("V002", f"total des débits différent du total des crédits (écart {ecart_total:.2f})"))

    # Continuité de la numérotation (si numérique)
    for journal, nums in numeros_par_journal.items():
        if nums and all(x.isdigit() for x in nums):
            ints = sorted(int(x) for x in nums)
            trous = (ints[-1] - ints[0] + 1) - len(ints)
            if trous:
                a(Anomalie(
                    "V009", f"journal {journal} : {trous} numéro(s) manquant(s) entre {ints[0]} et {ints[-1]}",
                    Severite.AVERTISSEMENT,
                ))

    return rapport
