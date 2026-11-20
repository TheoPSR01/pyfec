# pyfec

Lire, contrôler et analyser un Fichier des Écritures Comptables (FEC) en Python, sans aucune dépendance.

Depuis 2014, toute entreprise française qui tient sa comptabilité avec un logiciel doit pouvoir remettre son FEC à l'administration fiscale lors d'un contrôle (article L47 A du Livre des procédures fiscales). Le format est fixé par l'article A47 A-1 : 18 colonnes, séparateur tabulation ou barre verticale, dates au format AAAAMMJJ. Un FEC rejeté peut entraîner une amende de 5 000 € ou plus.

`pyfec` vérifie un FEC avant de l'envoyer, et sert aussi de point de départ pour des analyses (balance, totaux par journal, résultat) en contrôle de gestion ou en audit.

## Installation

```bash
pip install pyfec
```

En attendant la publication sur PyPI :

```bash
pip install git+https://github.com/TheoPSR01/pyfec.git
```

Python 3.9 ou plus récent.

## En ligne de commande

```bash
pyfec controle 123456782FEC20251231.txt
```

```
Fichier      : 123456782FEC20251231.txt
Encodage     : utf-8-sig  |  séparateur : tabulation  |  format : debit_credit
SIREN        : 123456782  |  clôture : 2025-12-31
Lignes       : 10  |  écritures : 4
Total débit  : 13 000,00
Total crédit : 13 000,00
Résultat     : 0 erreur(s), 0 avertissement(s)

FEC CONFORME aux contrôles effectués
```

Le code de sortie vaut 0 si le fichier est conforme et 1 sinon, ce qui permet d'utiliser la commande dans un script. Options utiles : `--tout` affiche aussi les avertissements, `--json` produit un rapport exploitable par un autre programme, `--debut` et `--fin` bornent l'exercice (la date de clôture est lue par défaut dans le nom du fichier).

```bash
pyfec balance 123456782FEC20251231.txt              # balance générale
pyfec balance 123456782FEC20251231.txt --niveau 1   # balance par classe
pyfec balance 123456782FEC20251231.txt --csv > balance.csv   # pour Excel
pyfec journaux 123456782FEC20251231.txt             # totaux par journal et résultat
```

## En Python

```python
from pyfec import lire_fec, valider, balance, resultat

fec = lire_fec("123456782FEC20251231.txt")
rapport = valider(fec)

print(rapport.est_valide)
for anomalie in rapport.erreurs:
    print(anomalie)

for ligne in balance(fec, niveau=3):
    print(ligne.compte_num, ligne.solde)

print("Résultat :", resultat(fec))
```

Chaque `LigneEcriture` expose les 18 champs déjà convertis : dates en `datetime.date`, montants en `Decimal` (jamais de `float` pour de la comptabilité).

## Contrôles effectués

Lecture du fichier :

| Code | Contrôle |
|------|----------|
| F001 | fichier vide |
| F002 | colonnes obligatoires manquantes |
| F003 | colonnes hors de l'ordre réglementaire (avertissement) |
| F004 | séparateur autre que tabulation ou barre verticale (avertissement) |
| F005 | nombre de champs différent de l'en-tête |
| F006 | EcritureDate, PieceDate ou ValidDate vide |
| F007 | date invalide |
| F008 | montant invalide |
| F009 | sens différent de D ou C (format Montant/Sens) |

Cohérence comptable :

| Code | Contrôle |
|------|----------|
| V001 | écriture déséquilibrée (débit ≠ crédit pour un même JournalCode et EcritureNum) |
| V002 | total des débits ≠ total des crédits |
| V003 | numéro de compte hors classes 1 à 8 ou trop court |
| V004 | champ obligatoire vide (JournalCode, JournalLib, EcritureNum, CompteNum, CompteLib, PieceRef, EcritureLib) |
| V005 | débit et crédit sur la même ligne, ou ligne à zéro (avertissement) |
| V006 | montant négatif (avertissement) |
| V007 | date de validation antérieure à la date d'écriture (avertissement) |
| V008 | écriture hors exercice |
| V009 | trou dans la numérotation d'un journal (avertissement) |
| V010 | plusieurs dates d'écriture dans une même écriture |
| V011 | compte auxiliaire sans libellé, ou l'inverse |
| V012 | lettrage sans date de lettrage (avertissement) |
| V013 | montant en devise sans code devise |
| V014 | nom de fichier différent de SIRENFECAAAAMMJJ (avertissement) |
| V015 | SIREN invalide selon la clé de Luhn (avertissement) |

Les deux variantes de l'article A47 A-1 sont reconnues (colonnes Debit/Credit, ou Montant/Sens). L'encodage est détecté automatiquement entre UTF-8, ISO 8859-15 et Windows-1252.

## Limites

`pyfec` ne remplace pas l'outil Test Compta Demat de la DGFiP, qui reste la référence. Les contrôles portent sur le format et la cohérence comptable, pas sur la régularité des écritures elles-mêmes. Les formats XML prévus pour certains régimes ne sont pas encore pris en charge.

## Contribuer

Les signalements de FEC mal lus (anonymisés) et les propositions de nouveaux contrôles sont les bienvenus dans les issues.

```bash
git clone https://github.com/TheoPSR01/pyfec.git
cd pyfec
pip install -e ".[dev]"
pytest
```

## Licence

MIT
