# -*- coding: utf-8 -*-
"""
Extraction des produits (code, qte, designation).

Parseur ligne par ligne generique (pas besoin d'un catalogue connu a
l'avance), avec :
  - fusion des lignes "orphelines" (sans code, meme produit sur 2 lignes)
  - fusion des designations coupees par un retour a la ligne au milieu
    d'une parenthese 
  - protection contre les pourcentages confondus avec des colonnes prix
    

Le catalogue (dict code -> designation) est optionnel : utilise pour
signaler les codes non reconnus.
"""
import re

from rapidfuzz import fuzz

# ------------------------------------------------------------------
# NETTOYAGE : annotations manuscrites type date de peremption "9/28"
# ------------------------------------------------------------------

_PEREMPTION_RE = re.compile(r"\b\d{1,2}\s*/\s*\d{2}\b(?!\d)")


def nettoyer_annotations_manuscrites(text):
    """Retire les tokens type '9/28', '12/27' (dates de peremption
    manuscrites), sans casser les N de BL du type '62264/2026'."""
    return _PEREMPTION_RE.sub(" ", text)


# ------------------------------------------------------------------
# PATTERNS DE LIGNE PRODUIT
# ------------------------------------------------------------------

_CODE_TOKEN = r"(?=[A-Z0-9\-]*\d)[A-Z0-9][A-Z0-9\-]{1,14}"

_LIGNE_FORMAT_B = re.compile(
    r"^[ \t]*(" + _CODE_TOKEN + r")[ \t]+(\d{1,4})\b(?!\s*[.,]\d)[ \t]+(?=[A-Za-zÀ-ÿ])(.*)$"
)

_LIGNE_FORMAT_A = re.compile(
    r"^[ \t]*(" + _CODE_TOKEN + r")[ \t]+([A-Za-zÀ-ÿ][^\n]*?)[ \t]+"
    r"\d{1,4}[.,]\d{2,3}[ \t]+(\d{1,4})\b(?!\s*[.,]\d)"
)

_LIGNE_ORPHELINE = re.compile(
    r"^[ \t]*(\d{1,4})\b(?!\s*[.,]\d)[ \t]+(?=[A-Za-zÀ-ÿ])(.*)$"
)

FUZZ_DESIGNATION_THRESHOLD = 80


def _couper_avant_prix(designation):
    """Coupe la designation avant la colonne de prix qui suit.
    Lookahead negatif (?!\\s*%) : un pourcentage type '0,05%' dans la
    designation elle-meme ne doit jamais etre confondu avec un prix.
    """
    m = re.search(r"[ \t]+\d{1,4}[.,]\d{2,3}\b(?!\s*%)", designation)
    if m:
        designation = designation[:m.start()]
    return re.sub(r"[ \t]{2,}", " ", designation).strip()


def extraire_produits(text, catalog=None):
    """Extrait la liste des produits (code, designation, quantite) d'un BL.

    Retourne (produits, alertes).
    """
    text = nettoyer_annotations_manuscrites(text)
    lignes = text.split("\n")

    produits = []
    index_par_code = {}
    alertes = []

    i, n = 0, len(lignes)
    while i < n:
        ligne = lignes[i]
        if not ligne.strip():
            i += 1
            continue

        m_b = _LIGNE_FORMAT_B.match(ligne)
        m_a = _LIGNE_FORMAT_A.match(ligne) if not m_b else None

        if m_b or m_a:
            if m_b:
                code, qte = m_b.group(1), int(m_b.group(2))
                designation = _couper_avant_prix(m_b.group(3))
            else:
                code = m_a.group(1)
                designation = m_a.group(2).strip()
                qte = int(m_a.group(3))

            # Continuation : designation se termine par une '(' non fermee
            while designation.count("(") > designation.count(")") and i + 1 < n:
                suivante = lignes[i + 1]
                if (not suivante.strip()
                        or _LIGNE_FORMAT_B.match(suivante)
                        or _LIGNE_FORMAT_A.match(suivante)):
                    break
                designation = designation.rstrip() + " " + suivante.strip()
                i += 1

            _ajouter_ou_cumuler(produits, index_par_code, code, designation, qte)
            i += 1
            continue

        m_orph = _LIGNE_ORPHELINE.match(ligne)
        if m_orph and produits:
            qte_orph, designation_orph = int(m_orph.group(1)), m_orph.group(2)
            designation_orph = _couper_avant_prix(designation_orph)
            dernier = produits[-1]
            score = fuzz.ratio(designation_orph.upper(), dernier["designation"].upper())
            if score >= FUZZ_DESIGNATION_THRESHOLD:
                dernier["quantite"] += qte_orph
            else:
                alertes.append(
                    f"Ligne orpheline non rattachee (score={score}): '{ligne.strip()}'"
                )
        i += 1

    if catalog:
        for p in produits:
            if p["code"] not in catalog:
                alertes.append(f"Code '{p['code']}' absent du catalogue.")

    return produits, alertes


def _ajouter_ou_cumuler(produits, index_par_code, code, designation, qte):
    """Ajoute un produit, ou cumule la quantite si le meme code a deja
    ete vu juste avant avec une designation similaire."""
    if code in index_par_code:
        idx = index_par_code[code]
        existant = produits[idx]
        score = fuzz.ratio(designation.upper(), existant["designation"].upper())
        if score >= FUZZ_DESIGNATION_THRESHOLD:
            existant["quantite"] += qte
            return
    produits.append({"code": code, "designation": designation, "quantite": qte})
    index_par_code[code] = len(produits) - 1