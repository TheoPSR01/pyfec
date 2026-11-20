"""Lecture d'un Fichier des Écritures Comptables."""

from __future__ import annotations

import csv
import io
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Union

from .model import (
    COLONNES_DEBIT_CREDIT,
    COLONNES_MONTANT_SENS,
    Anomalie,
    FichierFEC,
    LigneEcriture,
    Severite,
)

ENCODAGES = ("utf-8-sig", "iso-8859-15", "cp1252")
SEPARATEURS = ("\t", "|", ";")


def _decoder(data: bytes) -> tuple[str, str]:
    for enc in ENCODAGES:
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    # iso-8859-15 décode n'importe quel octet, on n'arrive jamais ici en pratique
    return data.decode("latin-1"), "latin-1"


def _detecter_separateur(premiere_ligne: str) -> str:
    comptes = {sep: premiere_ligne.count(sep) for sep in SEPARATEURS}
    return max(comptes, key=comptes.get)


def parse_date(valeur: str) -> Optional[date]:
    """Convertit une date AAAAMMJJ (ou AAAA-MM-JJ, JJ/MM/AAAA). Lève ValueError."""
    v = valeur.strip()
    if not v:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"date invalide : {valeur!r}")


def parse_montant(valeur: str) -> Decimal:
    """Convertit un montant à virgule ou à point décimal. Vide = 0. Lève ValueError."""
    v = valeur.strip().replace(" ", "").replace(" ", "")
    if not v:
        return Decimal("0")
    if "," in v and "." in v:
        # 1.234,56 -> 1234.56
        v = v.replace(".", "").replace(",", ".")
    else:
        v = v.replace(",", ".")
    try:
        return Decimal(v)
    except InvalidOperation as exc:
        raise ValueError(f"montant invalide : {valeur!r}") from exc


def lire_fec(source: Union[str, os.PathLike, bytes], separateur: Optional[str] = None) -> FichierFEC:
    """Lit un FEC et renvoie un :class:`FichierFEC`.

    La lecture ne s'arrête pas aux erreurs : chaque problème de format est
    consigné dans ``FichierFEC.anomalies`` et la ligne fautive est conservée
    avec les valeurs qui ont pu être converties.
    """
    if isinstance(source, bytes):
        data, chemin = source, "<bytes>"
    else:
        chemin = os.fspath(source)
        with open(chemin, "rb") as fh:
            data = fh.read()

    texte, encodage = _decoder(data)
    lignes_brutes = texte.splitlines()
    if not lignes_brutes or not lignes_brutes[0].strip():
        fec = FichierFEC(chemin, encodage, separateur or "\t", "inconnu", [])
        fec.anomalies.append(Anomalie("F001", "fichier vide"))
        return fec

    sep = separateur or _detecter_separateur(lignes_brutes[0])
    reader = csv.reader(io.StringIO(texte), delimiter=sep, quoting=csv.QUOTE_NONE)
    entete = [c.strip() for c in next(reader)]

    anomalies: list[Anomalie] = []
    entete_norm = [c.lower() for c in entete]
    if entete_norm == [c.lower() for c in COLONNES_DEBIT_CREDIT]:
        fmt = "debit_credit"
    elif entete_norm == [c.lower() for c in COLONNES_MONTANT_SENS]:
        fmt = "montant_sens"
    else:
        fmt = "debit_credit" if "debit" in entete_norm else "montant_sens"
        attendu = COLONNES_DEBIT_CREDIT if fmt == "debit_credit" else COLONNES_MONTANT_SENS
        manquantes = [c for c in attendu if c.lower() not in entete_norm]
        if manquantes:
            anomalies.append(Anomalie("F002", f"colonnes manquantes : {', '.join(manquantes)}", ligne=1))
        else:
            anomalies.append(Anomalie(
                "F003", "les colonnes ne sont pas dans l'ordre réglementaire",
                Severite.AVERTISSEMENT, ligne=1,
            ))
    if sep not in ("\t", "|"):
        anomalies.append(Anomalie(
            "F004", f"séparateur {sep!r} non prévu par l'article A47 A-1 (tabulation ou barre verticale)",
            Severite.AVERTISSEMENT, ligne=1,
        ))

    index = {nom: i for i, nom in enumerate(entete_norm)}
    fec = FichierFEC(chemin, encodage, sep, fmt, entete, anomalies=anomalies)

    for num, champs in enumerate(reader, start=2):
        if not any(c.strip() for c in champs):
            continue
        if len(champs) != len(entete):
            anomalies.append(Anomalie(
                "F005", f"{len(champs)} champs au lieu de {len(entete)}", ligne=num,
            ))
            champs = (champs + [""] * len(entete))[: len(entete)]

        def get(nom: str) -> str:
            i = index.get(nom.lower())
            return champs[i].strip() if i is not None else ""

        def get_date(nom: str, obligatoire: bool = False) -> Optional[date]:
            v = get(nom)
            if not v:
                if obligatoire:
                    anomalies.append(Anomalie("F006", f"{nom} vide", ligne=num))
                return None
            try:
                return parse_date(v)
            except ValueError:
                anomalies.append(Anomalie("F007", f"{nom} : date invalide {v!r}", ligne=num))
                return None

        def get_montant(nom: str) -> Decimal:
            try:
                return parse_montant(get(nom))
            except ValueError:
                anomalies.append(Anomalie("F008", f"{nom} : montant invalide {get(nom)!r}", ligne=num))
                return Decimal("0")

        if fmt == "debit_credit":
            debit, credit = get_montant("Debit"), get_montant("Credit")
        else:
            montant, sens = get_montant("Montant"), get("Sens").upper()
            if sens in ("D", "+1", "1"):
                debit, credit = montant, Decimal("0")
            elif sens in ("C", "-1"):
                debit, credit = Decimal("0"), montant
            else:
                anomalies.append(Anomalie("F009", f"Sens invalide {get('Sens')!r} (attendu D ou C)", ligne=num))
                debit = credit = Decimal("0")

        md = get("Montantdevise")
        try:
            montant_devise = parse_montant(md) if md else None
        except ValueError:
            anomalies.append(Anomalie("F008", f"Montantdevise : montant invalide {md!r}", ligne=num))
            montant_devise = None

        fec.lignes.append(LigneEcriture(
            ligne=num,
            journal_code=get("JournalCode"),
            journal_lib=get("JournalLib"),
            ecriture_num=get("EcritureNum"),
            ecriture_date=get_date("EcritureDate", obligatoire=True),
            compte_num=get("CompteNum"),
            compte_lib=get("CompteLib"),
            comp_aux_num=get("CompAuxNum"),
            comp_aux_lib=get("CompAuxLib"),
            piece_ref=get("PieceRef"),
            piece_date=get_date("PieceDate", obligatoire=True),
            ecriture_lib=get("EcritureLib"),
            debit=debit,
            credit=credit,
            ecriture_let=get("EcritureLet"),
            date_let=get_date("DateLet"),
            valid_date=get_date("ValidDate", obligatoire=True),
            montant_devise=montant_devise,
            idevise=get("Idevise"),
            brut=dict(zip(entete, champs)),
        ))

    return fec
