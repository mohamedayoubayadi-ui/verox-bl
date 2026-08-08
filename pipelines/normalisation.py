# -*- coding: utf-8 -*-
"""
Normalisation des nombres (virgule tunisienne) et des dates.
Utilise par extraction_entete.py et extraction_produits.py.
"""
from datetime import date


def normaliser_nombre(s):
    """'4 427,921' / '1 438.200' / '760,950' -> float. None si invalide.
    Convention tunisienne : virgule = separateur decimal, espace = milliers.
    """
    if s is None:
        return None
    s = str(s).strip()
    s = s.replace("\u00a0", " ").replace(" ", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def normaliser_date(j, m, a):
    """jj, mm, aa|aaaa (int) -> 'jj/mm/aaaa' str, ou None si invalide."""
    j, m, a = int(j), int(m), int(a)
    if a < 100:
        a += 2000
    try:
        date(a, m, j)
    except ValueError:
        return None
    return f"{j:02d}/{m:02d}/{a}"