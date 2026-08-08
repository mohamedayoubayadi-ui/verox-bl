# -*- coding: utf-8 -*-
"""
Orchestration complete.

Pipeline :
 1. extraction regex (entete + produits + noms) sur le texte OCR brut
 2. construction du BLDocument Pydantic -> validation de FORMAT
    (un champ mal forme est traite comme MANQUANT, pas comme une
    exception qui casse tout : on le met a None + on logue une alerte)
 3. si champs_manquants non vide -> un prompt DISTINCT par champ
    manquant (evite la dilution d'attention observee sur les prompts
    groupes)
 4. injection de la reponse dans le document + re-validation Pydantic
 5. JSON final (avec champs_manquants residuels -> file de revision
    manuelle)

appel_vlm est un CALLABLE fourni par l'appelant (services/ocr_client.py) :
une fonction qui appelle reellement le VLM avec un prompt et renvoie du
texte/JSON. Ce module ne fait aucun appel reseau : il reste testable
hors ligne.
"""
import json
import re
from typing import Callable, Optional

from pydantic import ValidationError

from pipelines.extraction_entete import extraire_champs_entete
from pipelines.extraction_produits import extraire_produits
from pipelines.extraction_noms import detecter_nom_fournisseur, detecter_nom_client
from pipelines.modele_bl import BLDocument


# ------------------------------------------------------------------
# 1+2. EXTRACTION REGEX -> CONSTRUCTION PYDANTIC ROBUSTE
# ------------------------------------------------------------------

def construire_bl_document(texte_ocr, catalog=None):
    """Renvoie (document: BLDocument, alertes: list[str])."""
    alertes = []

    champs = extraire_champs_entete(texte_ocr)
    produits_bruts, alertes_produits = extraire_produits(texte_ocr, catalog)
    alertes.extend(alertes_produits)

    nom_fournisseur = detecter_nom_fournisseur(texte_ocr)
    nom_client = detecter_nom_client(texte_ocr)

    data = {
        "num_bl": champs["num_bl"],
        "date_bl": champs["date_bl"],
        "nom_fournisseur": nom_fournisseur,
        "mf_fournisseur": champs["mf_fournisseur"],
        "nom_client": nom_client,
        "mf_client": champs["mf_client"],
        "produits": produits_bruts,
        "total_ttc": champs["total_ttc"],
    }

    document, alertes_validation = _construire_avec_repli(data)
    alertes.extend(alertes_validation)
    return document, alertes


def _construire_avec_repli(data: dict):
    """Construit un BLDocument ; si validation echoue sur un champ precis,
    le remet a None et reessaie (au lieu de tout perdre)."""
    alertes = []
    data = dict(data)
    for _ in range(10):
        try:
            return BLDocument(**data), alertes
        except ValidationError as e:
            corrige = False
            for err in e.errors():
                champ = err["loc"][0] if err["loc"] else None
                if champ in data and data.get(champ) is not None:
                    alertes.append(
                        f"Champ '{champ}' invalide ({err['msg']}) -> mis a None."
                    )
                    data[champ] = None if champ != "produits" else []
                    corrige = True
            if not corrige:
                raise
    return BLDocument(**data), alertes


# ------------------------------------------------------------------
# 3. PROMPTS DE RELANCE CIBLES (un par champ manquant)
# ------------------------------------------------------------------

_LIBELLES_CHAMPS = {
    "num_bl": (
        "le numero du Bon de Livraison, situe juste apres le libelle "
        "'Bon de Livraison N\u00b0' (en general en haut du document). "
        "Si rien n'est ecrit a cet endroit, reponds null."
    ),
    "date_bl": (
        "la date du Bon de Livraison, au format jj/mm/aaaa. "
        "C'est la date en haut du document, pres du nom de la ville "
        "(ex: 'SFAX Le : 26/05/2026')."
    ),
    "nom_fournisseur": (
        "le nom / raison sociale du FOURNISSEUR : l'entreprise qui "
        "emet le document, generalement ecrite en gros en haut a gauche."
    ),
    "mf_fournisseur": (
        "le matricule fiscal du FOURNISSEUR. Format specifique avec "
        "des barres obliques, exemple : 1234567X/A/M/000 (chiffres + "
        "1 lettre + / + lettre + / + lettre + / + 3 chiffres). "
        "Il se trouve pres du nom du fournisseur, souvent apres 'M.F :'."
    ),
    "nom_client": (
        "le nom du CLIENT : la pharmacie ou le destinataire de la "
        "livraison, generalement indique a droite ou en dessous du "
        "libelle 'Doit au' ou 'Nom Client'."
    ),
    "mf_client": (
        "le matricule fiscal du CLIENT. Format tres specifique avec "
        "des barres obliques, exemple : 1234567X/A/M/000 (chiffres + "
        "1 lettre + / + lettre + / + lettre + / + 3 chiffres).\n"
        "Ce n'est PAS le 'Code Client' (qui est un simple nombre sans "
        "lettre ni barre oblique, ex: 4110240) - ne pas confondre les deux."
    ),
    "total_ttc": (
        "le montant TOTAL TTC final du document, generalement la "
        "derniere ligne du recapitulatif des totaux en bas de page "
        "(souvent notee 'TOTAL TTC'). Ecris le nombre avec un POINT "
        "decimal, jamais de virgule (ex: 401.553).\n"
        "Ce n'est pas le montant d'une seule ligne de produit du tableau."
    ),
    "produits": (
        "la liste des produits : code, quantite, designation, pour "
        "chaque ligne du tableau."
    ),
}


def generer_prompts_relance(document: BLDocument) -> dict:
    """Un prompt DISTINCT par champ manquant. Retourne {} si rien ne manque."""
    manquants = document.champs_manquants
    if not manquants:
        return {}

    prompts = {}
    for champ in manquants:
        libelle = _LIBELLES_CHAMPS[champ]
        if champ == "produits":
            prompts[champ] = (
                "Analyse ce document et extrais la LISTE COMPLETE des produits "
                "(tableau des articles). Reponds STRICTEMENT en JSON valide, "
                'sans texte avant ni apres, format : '
                '{"produits": [{"code": ..., "quantite": ..., "designation": ...}, ...]}'
            )
        else:
            prompts[champ] = (
                f"Analyse ce document et extrais UNIQUEMENT le champ suivant :\n"
                f"  {libelle}\n\n"
                f'Reponds STRICTEMENT en JSON valide, sans texte avant ni apres, '
                f'format exact : {{"{champ}": valeur_ou_null}}.\n'
                "Si le champ est vraiment introuvable, mets sa valeur a null. "
                "N'utilise jamais de virgule dans un nombre (point decimal uniquement)."
            )
    return prompts


# ------------------------------------------------------------------
# 4. INJECTION DE LA REPONSE DE LA 2E PASSE
# ------------------------------------------------------------------

def _normaliser_pour_comparaison(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper()) if s else s


def injecter_reponse_vlm(document: BLDocument, reponse_json: dict):
    """Fusionne la reponse JSON de la 2e passe dans le document, puis
    re-valide. N'ecrase jamais un champ deja rempli : ne comble que les
    None existants.
    """
    alertes = []
    data = document.model_dump()
    codes_produits = {p["code"] for p in data.get("produits", [])}
    mf_four_norm = _normaliser_pour_comparaison(data.get("mf_fournisseur"))

    for champ in document.champs_manquants:
        if champ not in reponse_json or reponse_json[champ] is None:
            continue
        valeur = reponse_json[champ]

        if champ == "num_bl" and str(valeur).strip() in codes_produits:
            alertes.append(
                f"num_bl rejete : '{valeur}' correspond a un code produit "
                "deja extrait (confusion probable du VLM)."
            )
            continue

        if champ == "mf_client" and mf_four_norm and \
                _normaliser_pour_comparaison(valeur) == mf_four_norm:
            alertes.append(
                f"mf_client rejete : '{valeur}' identique au mf_fournisseur "
                "(confusion probable du VLM)."
            )
            continue

        data[champ] = valeur

    document_final, alertes_validation = _construire_avec_repli(data)
    alertes.extend(alertes_validation)
    return document_final, alertes


# ------------------------------------------------------------------
# 5. PIPELINE COMPLET
# ------------------------------------------------------------------

def traiter_bl(texte_ocr_brut: str,
               appel_vlm: Optional[Callable[[str], dict]] = None,
               catalog=None) -> dict:
    """Pipeline complet : 1ere passe regex -> (si besoin) 2e passe VLM
    ciblee -> JSON final avec statut de completude.
    """
    document, alertes = construire_bl_document(texte_ocr_brut, catalog)

    if not document.est_complet and appel_vlm is not None:
        prompts = generer_prompts_relance(document)
        reponse_aggregee = {}
        for champ, prompt in prompts.items():
            try:
                reponse = appel_vlm(prompt)
                if isinstance(reponse, str):
                    reponse = json.loads(reponse)
                if champ in reponse:
                    reponse_aggregee[champ] = reponse[champ]
            except Exception as e:
                alertes.append(f"Echec 2e passe pour '{champ}' : {e}")

        document, alertes_2 = injecter_reponse_vlm(document, reponse_aggregee)
        alertes.extend(alertes_2)

    resultat = document.to_dict_avec_statut()
    resultat["alertes"] = alertes
    return resultat