# -*- coding: utf-8 -*-
"""
Pipeline d'execution complet : gestion du serveur vLLM et traitement
d'un Bon de Livraison de bout en bout.

Etapes :
  1. Lancement du serveur vLLM (hebergeant GLM-OCR)
  2. 1ere passe : OCR brut de l'image ("extraire le texte fidelement")
  3. Extraction structuree + validation (voir pipelines/orchestration.py)
  4. Si des champs manquent : 2e passe GLM-OCR ciblee (JSON strict)
  5. Retour du JSON final
"""

import base64
import json
import os
import re
import subprocess
import time

import requests
from openai import OpenAI

from pipelines.orchestration import traiter_bl

MODEL_ID    = "zai-org/GLM-OCR"
IMAGE_PATH  = os.environ.get(
    "BL_IMAGE_PATH",
    "/kaggle/input/datasets/medayoubayedi/bl-med/8.jpeg",
)
SERVER_PORT = 8080
SERVER_URL  = f"http://localhost:{SERVER_PORT}"


# ==========================================================
# ETAPE 1 : lancement du serveur vLLM (TON CODE, inchange)
# ==========================================================
def start_server() -> subprocess.Popen:
    process = subprocess.Popen([
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model",                  MODEL_ID,
        "--dtype",                  "float16",
        "--max-model-len",          "8192",
        "--max-num-batched-tokens", "32768",
        "--gpu-memory-utilization", "0.85",
        "--port",                   str(SERVER_PORT),
        "--trust-remote-code",
    ])
    print("Démarrage du serveur vLLM...")
    for _ in range(24):
        time.sleep(5)
        try:
            r = requests.get(f"{SERVER_URL}/health", timeout=2)
            if r.status_code == 200:
                print("Serveur prêt.")
                return process
        except requests.exceptions.ConnectionError:
            pass
    raise RuntimeError("Le serveur vLLM n'a pas démarré dans les temps.")


# ==========================================================
# ETAPE 2 : appel generique au VLM (image + prompt -> texte brut)
# ==========================================================
def appeler_glm_ocr_brut(image_path: str, prompt: str, client: OpenAI,
                          max_tokens: int = 2000) -> str:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ]
        }],
        max_tokens=max_tokens,
        temperature=0,
    )
    return response.choices[0].message.content


# ==========================================================
# ETAPE 3 : petit nettoyage de la reponse JSON du VLM
# ==========================================================
def parser_reponse_json(texte: str) -> dict:
    texte = texte.strip()
    texte = re.sub(r"^```(?:json)?\s*", "", texte)
    texte = re.sub(r"\s*```$", "", texte)
    return json.loads(texte)


# ==========================================================
# ETAPE 4 : PIPELINE COMPLET SUR UNE IMAGE
# ==========================================================
def traiter_un_bl(image_path: str, client: OpenAI, catalog=None) -> dict:
    """
    1) OCR brut de l'image (prompt generale)
    2) extraction regex + Pydantic (tes fichiers)
    3) si champs manquants -> 2e appel GLM-OCR avec une prompt PRECISE,
       generee automatiquement par orchestration.generer_prompts_relance
    4) JSON final
    """
    t0 = time.time()
    texte_brut = appeler_glm_ocr_brut(
        image_path, "extraire le texte fidelement", client
    )
    print(f"[1ere passe OCR brut] {round(time.time() - t0, 2)}s")

    def appel_glm_ocr_pour_champs_manquants(prompt: str) -> dict:
        t1 = time.time()
        reponse_texte = appeler_glm_ocr_brut(
            image_path, prompt, client, max_tokens=800
        )
        print(f"[2e passe cibl\u00e9e] {round(time.time() - t1, 2)}s")
        print("Reponse brute VLM (2e passe) :", reponse_texte)
        return parser_reponse_json(reponse_texte)

    resultat = traiter_bl(
        texte_brut,
        appel_vlm=appel_glm_ocr_pour_champs_manquants,
        catalog=catalog,
    )
    resultat["texte_ocr_brut"] = texte_brut
    return resultat


# ==========================================================
# POINT D'ENTREE
# ==========================================================
if __name__ == "__main__":
    server = start_server()
    client = OpenAI(base_url=f"{SERVER_URL}/v1", api_key="none")

    resultat = traiter_un_bl(IMAGE_PATH, client, catalog=None)

    print("=" * 60)
    print(json.dumps(resultat, ensure_ascii=False, indent=2))
    print("=" * 60)