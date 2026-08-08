# -*- coding: utf-8 -*-
"""
Modele Pydantic du BL.
- Tous les champs "en-tete" sont Optional -> permet de construire le
  JSON meme incomplet.
- Validators de FORMAT (date valide, MF au bon format, num_bl qui ne
  ressemble ni a un montant ni a un MF, montants/quantites positifs).
- Validator croise : coherence entre champs (num_bl != code produit,
  mf_client != mf_fournisseur).
- champs_manquants : liste des champs top-level encore a None.
"""
import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

_MF_FORMAT_RE = re.compile(r"^\d{6,9}[A-Z]/[A-Z]/[A-Z]/\d{3}$")

# Un num_bl ne doit jamais ressembler a un montant en dinars
_MONTANT_FORMAT_RE = re.compile(r"^\d+[.,]\d{3}$")


class Produit(BaseModel):
    code: str
    designation: str
    quantite: int = Field(gt=0)


class BLDocument(BaseModel):
    num_bl: Optional[str] = None
    date_bl: Optional[str] = None
    nom_fournisseur: Optional[str] = None
    mf_fournisseur: Optional[str] = None
    nom_client: Optional[str] = None
    mf_client: Optional[str] = None
    produits: List[Produit] = Field(default_factory=list)
    total_ttc: Optional[float] = Field(default=None, gt=0)

    @field_validator("num_bl")
    @classmethod
    def _valider_num_bl(cls, v):
        if v is None:
            return v
        v = str(v).strip()
        if _MONTANT_FORMAT_RE.match(v):
            raise ValueError(
                f"num_bl invalide : '{v}' a un format monetaire "
                "(virgule/point + 3 decimales), pas un numero de document"
            )
        if _MF_FORMAT_RE.match(v):
            raise ValueError(
                f"num_bl invalide : '{v}' a un format de matricule fiscal, "
                "pas un numero de document"
            )
        return v

    @field_validator("date_bl")
    @classmethod
    def _valider_date(cls, v):
        if v is None:
            return v
        try:
            datetime.strptime(v, "%d/%m/%Y")
        except ValueError:
            raise ValueError(f"date_bl invalide : '{v}' (attendu jj/mm/aaaa)")
        return v

    @field_validator("mf_fournisseur", "mf_client")
    @classmethod
    def _valider_mf(cls, v):
        if v is None:
            return v
        if not _MF_FORMAT_RE.match(v):
            raise ValueError(f"matricule fiscal invalide : '{v}'")
        return v

    @model_validator(mode="after")
    def _verifier_coherence(self):
        if self.num_bl is not None:
            codes = {p.code.strip() for p in self.produits}
            if self.num_bl.strip() in codes:
                self.num_bl = None

        if self.mf_client is not None and self.mf_fournisseur is not None:
            norm = lambda s: re.sub(r"[^A-Z0-9]", "", s.upper())
            if norm(self.mf_client) == norm(self.mf_fournisseur):
                self.mf_client = None

        return self

    @property
    def champs_manquants(self) -> List[str]:
        champs_a_verifier = [
            "num_bl", "date_bl",
            "nom_fournisseur", "mf_fournisseur",
            "nom_client", "mf_client",
            "total_ttc",
        ]
        manquants = [c for c in champs_a_verifier if getattr(self, c) is None]
        if not self.produits:
            manquants.append("produits")
        return manquants

    @property
    def est_complet(self) -> bool:
        return len(self.champs_manquants) == 0

    def to_dict_avec_statut(self) -> dict:
        d = self.model_dump()
        d["champs_manquants"] = self.champs_manquants
        d["est_complet"] = self.est_complet
        return d