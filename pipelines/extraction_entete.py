# -*- coding: utf-8 -*-
"""
Extraction des champs "en-tete" du BL :
    - numero de BL (meme ligne OU ligne suivante)
    - date du BL
    - matricule fiscal fournisseur / client (positionnel)
    - total TTC (plusieurs libelles possibles)
"""
import re

from pipelines.normalisation import normaliser_nombre, normaliser_date

# ------------------------------------------------------------------
# DATE DU BL
# ------------------------------------------------------------------


def detecter_date(text):
    """Detecte la date du BL (jj/mm/aaaa) ou None."""
    m = re.search(
        r"Date\s*[:\-]?\s*(\d{1,2})\s*[/.\- ]\s*(\d{1,2})\s*[/.\- ]\s*(\d{2,4})",
        text, re.IGNORECASE)
    if not m:
        m = re.search(
            r"(?:Le|LE)\s*[:\-]?\s*(\d{1,2})\s*[/.\- ]\s*(\d{1,2})\s*[/.\- ]\s*(\d{2,4})",
            text)
    if not m:
        m = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})\b", text)
    if not m:
        return None
    return normaliser_date(m.group(1), m.group(2), m.group(3))


# ------------------------------------------------------------------
# NUMERO DE BL
# ------------------------------------------------------------------

_LABEL = r"(?i:(?:BON\s+DE\s+LIVRAISON|FACTURE)[^\n]*?N\s*[°ºo]?\s*[:\-]?)"
_VALUE = r"([A-Z]{1,5}\d[A-Z0-9]*|\d{3,}(?:\s*/\s*\d{2,4})?)"

_BL_RE_SAMELINE = re.compile(_LABEL + r"[ \t]*" + _VALUE)
_BL_RE_NEXTLINE = re.compile(_LABEL + r"[ \t]*\n(?:[ \t]*\n)?[ \t]*" + _VALUE)
_CMD_RE = re.compile(r"(?i:Commande\s*N\s*[°ºo]?\s*[:\-]?)\s*(\d{3,})")


def detecter_bl(text, fallback_commande=False):
    """N de BL (str normalisee) ou None.

    NOTE : fallback_commande=False par defaut. Le N de Commande n'est PAS
    le N de BL -> l'utiliser comme substitut silencieux produirait une
    fausse valeur et empecherait le declenchement de la 2e passe VLM
    ciblee sur le vrai champ manquant.
    """
    m = _BL_RE_SAMELINE.search(text)
    if not m:
        m = _BL_RE_NEXTLINE.search(text)
    if m:
        val = re.sub(r"\s*/\s*", "/", m.group(1).strip())
        return val
    if fallback_commande:
        m = _CMD_RE.search(text)
        if m:
            return m.group(1)
    return None


# ------------------------------------------------------------------
# MATRICULE FISCAL FOURNISSEUR / CLIENT (positionnel)
# ------------------------------------------------------------------

_MF_RE = re.compile(
    r"\b(\d{6,9}[A-Z])\s*/?\s*([A-Z])\s*/?\s*([A-Z])\s*/?\s*(\d{3})\b"
)

_CLIENT_MARKERS = re.compile(
    r"(?i:Doit\s+au|Code\s+Client|Nom\s*&?\s*Pr[ée]nom|Nom\s+Client)"
)


def _normaliser_mf(match):
    return f"{match.group(1)}/{match.group(2)}/{match.group(3)}/{match.group(4)}"


def detecter_mf_fournisseur_client(text):
    """Retourne (mf_fournisseur, mf_client).
    Regle : le 1er MF trouve AVANT le marqueur client = fournisseur,
            le 1er MF trouve APRES ce marqueur = client.
    Si aucun marqueur client trouve -> 1er MF = fournisseur, 2e MF = client (repli).
    """
    marker = _CLIENT_MARKERS.search(text)
    all_mf = list(_MF_RE.finditer(text))

    if not all_mf:
        return None, None

    if marker:
        before = [m for m in all_mf if m.start() < marker.start()]
        after = [m for m in all_mf if m.start() >= marker.start()]
        mf_fournisseur = _normaliser_mf(before[0]) if before else None
        mf_client = _normaliser_mf(after[0]) if after else None
        return mf_fournisseur, mf_client

    mf_fournisseur = _normaliser_mf(all_mf[0])
    mf_client = _normaliser_mf(all_mf[1]) if len(all_mf) > 1 else None
    return mf_fournisseur, mf_client


# ------------------------------------------------------------------
# TOTAL TTC
# ------------------------------------------------------------------

_TOTAL_LABELS = [
    r"Total\s+T\.?T\.?C\.?",
    r"TOTAL\s+TTC",
    r"TOTAL\s+BL",
    r"Mnt\.?\s*Pharm\.?\s*TTC[^\n]*?NET",
]


def detecter_total_ttc(text):
    """Total TTC du BL (float) ou None. Cherche les libelles par ordre de priorite."""
    for label in _TOTAL_LABELS:
        pattern = re.compile(label + r"[^\d]{0,25}(\d[\d\s\u00a0]*[.,]\d{2,3})",
                              re.IGNORECASE)
        m = pattern.search(text)
        if m:
            val = normaliser_nombre(m.group(1))
            if val is not None:
                return val
    return None


# ------------------------------------------------------------------
# WRAPPER
# ------------------------------------------------------------------


def extraire_champs_entete(text):
    mf_four, mf_client = detecter_mf_fournisseur_client(text)
    return {
        "num_bl": detecter_bl(text),
        "date_bl": detecter_date(text),
        "mf_fournisseur": mf_four,
        "mf_client": mf_client,
        "total_ttc": detecter_total_ttc(text),
    }