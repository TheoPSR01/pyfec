"""Interface en ligne de commande : ``pyfec controle`` et ``pyfec balance``."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from . import __version__
from .analyse import balance, ecrire_balance_csv, resultat, totaux_par_journal
from .reader import lire_fec, parse_date
from .validator import valider


def _date(v: str) -> date:
    d = parse_date(v)
    if d is None:
        raise argparse.ArgumentTypeError("date vide")
    return d


def _fmt(x) -> str:
    return f"{x:,.2f}".replace(",", " ").replace(".", ",")


def cmd_controle(args) -> int:
    fec = lire_fec(args.fichier, separateur=args.separateur)
    rapport = valider(fec, debut_exercice=args.debut, fin_exercice=args.fin)
    if args.json:
        print(json.dumps({
            "fichier": fec.chemin,
            "valide": rapport.est_valide,
            "lignes": len(fec.lignes),
            "ecritures": rapport.nb_ecritures,
            "total_debit": str(fec.total_debit),
            "total_credit": str(fec.total_credit),
            "anomalies": [
                {"code": a.code, "severite": a.severite.value, "ligne": a.ligne, "message": a.message}
                for a in rapport.anomalies
            ],
        }, ensure_ascii=False, indent=2))
    else:
        print(rapport.resume())
        anomalies = rapport.anomalies if args.tout else rapport.erreurs
        if anomalies:
            print()
            for a in anomalies[: args.max]:
                print(a)
            if len(anomalies) > args.max:
                print(f"... et {len(anomalies) - args.max} autre(s) (option --max)")
        if not args.tout and rapport.avertissements:
            print(f"\n{len(rapport.avertissements)} avertissement(s) masqué(s), option --tout pour les afficher")
    return 0 if rapport.est_valide else 1


def cmd_balance(args) -> int:
    fec = lire_fec(args.fichier, separateur=args.separateur)
    lignes = balance(fec, niveau=args.niveau)
    if args.csv:
        ecrire_balance_csv(lignes, sys.stdout)
        return 0
    largeur = max((len(b.compte_num) for b in lignes), default=8)
    print(f"{'Compte':<{largeur}}  {'Libellé':<35} {'Débit':>15} {'Crédit':>15} {'Solde':>15}")
    for b in lignes:
        print(f"{b.compte_num:<{largeur}}  {b.compte_lib[:35]:<35} {_fmt(b.debit):>15} {_fmt(b.credit):>15} {_fmt(b.solde):>15}")
    print(f"{'TOTAL':<{largeur}}  {'':<35} {_fmt(fec.total_debit):>15} {_fmt(fec.total_credit):>15}")
    return 0


def cmd_journaux(args) -> int:
    fec = lire_fec(args.fichier, separateur=args.separateur)
    print(f"{'Code':<6} {'Libellé':<30} {'Écritures':>10} {'Débit':>15} {'Crédit':>15}")
    for code, lib, nb, d, c in totaux_par_journal(fec):
        print(f"{code:<6} {lib[:30]:<30} {nb:>10} {_fmt(d):>15} {_fmt(c):>15}")
    print(f"\nRésultat (classes 7 - 6) : {_fmt(resultat(fec))}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pyfec", description="Contrôle et analyse d'un Fichier des Écritures Comptables.")
    p.add_argument("--version", action="version", version=f"pyfec {__version__}")
    sub = p.add_subparsers(dest="commande", required=True)

    def commun(sp):
        sp.add_argument("fichier", help="chemin du FEC (.txt ou .csv)")
        sp.add_argument("--separateur", help="forcer le séparateur (détecté par défaut)")

    c = sub.add_parser("controle", help="contrôler la conformité du FEC")
    commun(c)
    c.add_argument("--debut", type=_date, help="date d'ouverture de l'exercice (AAAAMMJJ)")
    c.add_argument("--fin", type=_date, help="date de clôture (par défaut : lue dans le nom du fichier)")
    c.add_argument("--tout", action="store_true", help="afficher aussi les avertissements")
    c.add_argument("--max", type=int, default=50, help="nombre maximal d'anomalies affichées")
    c.add_argument("--json", action="store_true", help="sortie JSON")
    c.set_defaults(func=cmd_controle)

    b = sub.add_parser("balance", help="afficher la balance générale")
    commun(b)
    b.add_argument("--niveau", type=int, help="regrouper sur les N premiers caractères du compte")
    b.add_argument("--csv", action="store_true", help="sortie CSV (point-virgule, virgule décimale)")
    b.set_defaults(func=cmd_balance)

    j = sub.add_parser("journaux", help="totaux par journal et résultat")
    commun(j)
    j.set_defaults(func=cmd_journaux)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"pyfec : fichier introuvable : {exc.filename}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
