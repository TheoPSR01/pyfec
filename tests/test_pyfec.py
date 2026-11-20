from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from pyfec import balance, lire_fec, parse_date, parse_montant, resultat, siren_valide, valider
from pyfec.cli import main

DATA = Path(__file__).parent / "data"
EXEMPLE = DATA / "123456782FEC20251231.txt"
ENTETE = (
    "JournalCode|JournalLib|EcritureNum|EcritureDate|CompteNum|CompteLib|CompAuxNum|CompAuxLib|"
    "PieceRef|PieceDate|EcritureLib|Debit|Credit|EcritureLet|DateLet|ValidDate|Montantdevise|Idevise"
)


def fec_bytes(*lignes, entete=ENTETE, encoding="utf-8"):
    return ("\n".join((entete,) + lignes) + "\n").encode(encoding)


def codes(rapport):
    return {a.code for a in rapport.anomalies}


# --- conversions -----------------------------------------------------------

@pytest.mark.parametrize("brut,attendu", [
    ("1234,56", Decimal("1234.56")),
    ("1234.56", Decimal("1234.56")),
    ("1.234,56", Decimal("1234.56")),
    ("1 234,56", Decimal("1234.56")),
    ("", Decimal("0")),
    ("-12,5", Decimal("-12.5")),
    (" 000000000003000,00", Decimal("3000.00")),   # format d'export Odoo
    ("-000000000001000,00", Decimal("-1000.00")),
])
def test_parse_montant(brut, attendu):
    assert parse_montant(brut) == attendu


def test_parse_montant_invalide():
    with pytest.raises(ValueError):
        parse_montant("12a")


def test_parse_date():
    assert parse_date("20251231") == date(2025, 12, 31)
    assert parse_date("31/12/2025") == date(2025, 12, 31)
    assert parse_date("") is None
    with pytest.raises(ValueError):
        parse_date("20251332")


def test_siren():
    assert siren_valide("123456782")
    assert not siren_valide("123456789")
    assert not siren_valide("12345")


# --- fichier conforme ------------------------------------------------------

def test_exemple_conforme():
    fec = lire_fec(EXEMPLE)
    assert fec.separateur == "\t"
    assert fec.format == "debit_credit"
    assert len(fec.lignes) == 10
    rapport = valider(fec)
    assert rapport.est_valide, [str(a) for a in rapport.anomalies]
    assert rapport.siren == "123456782"
    assert rapport.date_cloture == date(2025, 12, 31)
    assert rapport.nb_ecritures == 4
    assert fec.total_debit == fec.total_credit == Decimal("13000.00")


def test_balance_et_resultat():
    fec = lire_fec(EXEMPLE)
    b = {l.compte_num: l for l in balance(fec)}
    assert b["512000"].solde == Decimal("11200.00")
    assert b["411000"].solde == 0
    assert resultat(fec) == Decimal("500.00")  # 1000 de ventes - 500 d'achats
    classes = {l.compte_num: l.solde for l in balance(fec, niveau=1)}
    assert classes["7"] == Decimal("-1000.00")


# --- anomalies -------------------------------------------------------------

def test_ecriture_desequilibree():
    data = fec_bytes(
        "VT|Ventes|1|20250115|411000|Clients|||F1|20250115|Fact|100,00|0,00|||20250115||",
        "VT|Ventes|1|20250115|706000|Ventes|||F1|20250115|Fact|0,00|90,00|||20250115||",
    )
    r = valider(lire_fec(data))
    assert not r.est_valide
    assert {"V001", "V002"} <= codes(r)


def test_colonnes_manquantes():
    data = fec_bytes("VT|1|20250115", entete="JournalCode|EcritureNum|EcritureDate")
    r = valider(lire_fec(data))
    assert "F002" in codes(r)


def test_champs_vides_et_dates():
    data = fec_bytes(
        "VT||1|2025-13-01|9ABC|Clients|C1||F1|20250115||100|0|||20250115||",
        "VT|Ventes|1|20250115|706000|Ventes|||F1|20250115|Fact|0|100|||20250115||",
    )
    r = valider(lire_fec(data))
    assert {"V004", "V003", "V011", "F007"} <= codes(r)


def test_date_hors_exercice():
    data = fec_bytes(
        "VT|Ventes|1|20260105|411000|Clients|||F1|20260105|Fact|100|0|||20260105||",
        "VT|Ventes|1|20260105|706000|Ventes|||F1|20260105|Fact|0|100|||20260105||",
    )
    r = valider(lire_fec(data), fin_exercice=date(2025, 12, 31))
    assert "V008" in codes(r)


def test_trou_de_numerotation():
    lignes = []
    for n in (1, 2, 5):
        lignes += [
            f"VT|Ventes|{n}|20250115|411000|Clients|||F{n}|20250115|Fact|100|0|||20250115||",
            f"VT|Ventes|{n}|20250115|706000|Ventes|||F{n}|20250115|Fact|0|100|||20250115||",
        ]
    r = valider(lire_fec(fec_bytes(*lignes)))
    assert r.est_valide
    assert any(a.code == "V009" and "2 numéro" in a.message for a in r.avertissements)


def test_format_montant_sens_et_latin9():
    entete = ENTETE.replace("Debit|Credit", "Montant|Sens")
    data = fec_bytes(
        "VT|Ventes|1|20250115|411000|Clients|||F1|20250115|Facture été|120|D|||20250115||",
        "VT|Ventes|1|20250115|706000|Ventes|||F1|20250115|Facture été|120|C|||20250115||",
        entete=entete, encoding="iso-8859-15",
    )
    fec = lire_fec(data)
    assert fec.format == "montant_sens"
    assert fec.encodage == "iso-8859-15"
    assert fec.lignes[0].ecriture_lib == "Facture été"
    assert valider(fec).est_valide


def test_nombre_de_champs():
    data = fec_bytes("VT|Ventes|1|20250115|411000")
    assert "F005" in codes(valider(lire_fec(data)))


def test_fichier_vide():
    assert "F001" in codes(valider(lire_fec(b"")))


# --- ligne de commande -----------------------------------------------------

def test_cli_controle(capsys):
    assert main(["controle", str(EXEMPLE)]) == 0
    assert "FEC CONFORME" in capsys.readouterr().out


def test_cli_balance_csv(capsys):
    assert main(["balance", str(EXEMPLE), "--csv"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("CompteNum;")
    assert "512000;Banque;11200,00;0,00;11200,00;0,00" in out


def test_cli_fichier_absent(capsys):
    assert main(["controle", "absent.txt"]) == 2
