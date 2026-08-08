# -*- coding: utf-8 -*-
"""
Extraction du NOM fournisseur et du NOM client.
"""
import re

# Lignes clairement pas un nom d'entreprise (adresse, tel, etc.) + titres
# de document frequents a ne jamais confondre avec la raison sociale.
_EXCLUSIONS_FOURNISSEUR = re.compile(
    r"(?i:^(route|adresse|tel|email|mf|m\.f|code\s+t\.?v\.?a|"
    r"bon\s+de\s+livraison|facture|bl\s*n|r[ée]publique\s+tunisienne|"
    r"original|copie|page\s*n)\b)"
)


def detecter_nom_fournisseur(text):
    """La toute premiere ligne non vide qui ne matche aucune exclusion
    (raison sociale en en-tete)."""
    for ligne in text.split("\n"):
        ligne = ligne.strip()
        if not ligne:
            continue
        if _EXCLUSIONS_FOURNISSEUR.match(ligne):
            continue
        return ligne
    return None


_CLIENT_NOM_PATTERNS = [
    r"(?i:Doit\s+au\s*:?)\s*([^\n(]+)",
    r"(?i:Nom\s*&?\s*Pr[ée]nom\s*:?)\s*\n?\s*([^\n]+)",
    r"(?i:Nom\s+Client\s*:?)\s*([^\n]+)",
]

_CODE_CLIENT_RE = re.compile(r"(?i:Code\s+Client\s*:?\s*\d+)\s*\n\s*([^\n]+)")


def detecter_nom_client(text):
    for pattern in _CLIENT_NOM_PATTERNS:
        m = re.search(pattern, text)
        if m:
            nom = m.group(1).strip()
            if nom:
                return nom
    m = _CODE_CLIENT_RE.search(text)
    if m:
        nom = m.group(1).strip()
        if nom:
            return nom
    return None