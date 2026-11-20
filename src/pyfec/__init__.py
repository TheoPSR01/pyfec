"""pyfec : lire, contrôler et analyser un Fichier des Écritures Comptables (FEC)."""

from .analyse import balance, ecrire_balance_csv, resultat, solde_classes, totaux_par_journal
from .model import Anomalie, FichierFEC, LigneEcriture, Severite
from .reader import lire_fec, parse_date, parse_montant
from .validator import Rapport, siren_valide, valider

__version__ = "0.1.0"

__all__ = [
    "Anomalie",
    "FichierFEC",
    "LigneEcriture",
    "Rapport",
    "Severite",
    "balance",
    "ecrire_balance_csv",
    "lire_fec",
    "parse_date",
    "parse_montant",
    "resultat",
    "siren_valide",
    "solde_classes",
    "totaux_par_journal",
    "valider",
]
