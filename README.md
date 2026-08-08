# Verox BL — Delivery Note Extraction Pipeline

Automated extraction of delivery note data (supplier, client, products,
amounts) from photos, using a hybrid pipeline: a vision-language model
(GLM-OCR, served via vLLM) reads the document, then regex-based parsing
with Pydantic validation structures the output, with a targeted second
VLM-OCR pass for any field that remains missing or invalid.

> **Status**: proof of concept. The extraction pipeline and the GLM-OCR
> integration are implemented and have been tested end-to-end on real
> delivery notes (NVIDIA Tesla T4, Kaggle). The backend API and
> database layer are not yet implemented (see Roadmap below).

## What's implemented

- **`pipelines/`** — core extraction and validation logic:
  - `normalisation.py` — number/date normalization (Tunisian comma
    decimal format)
  - `extraction_entete.py` — delivery note number, date, tax ID
    (supplier/client), total amount
  - `extraction_produits.py` — product lines (code, quantity,
    description)
  - `extraction_noms.py` — supplier/client name detection
  - `modele_bl.py` — Pydantic data model with format validation and
    cross-field consistency checks (e.g. a delivery note number can't
    look like a monetary amount or a tax ID)
  - `orchestration.py` — orchestrates the full flow: regex extraction
    first, then a targeted VLM-OCR fallback (one prompt per missing
    field) for anything the regex pass couldn't extract or validate

  This part runs entirely on CPU and executes in milliseconds.

- **`services/pipeline_verox.py`** — vLLM server management and
  GLM-OCR calls (raw OCR pass + targeted fallback pass), tested
  end-to-end on an NVIDIA Tesla T4 (Kaggle)

## What's planned (not yet implemented)

- **`referances/`** — reference datasets (known suppliers, pharmacies,
  medications) considered for cross-validation of extracted fields;
  under evaluation, not yet wired into the pipeline
- **`src/`** — backend API (FastAPI) to expose the pipeline over HTTP
- **Database** (PostgreSQL / SQLite) — persistence of processed
  delivery notes

## Pipeline

1. Raw OCR reading of the image via GLM-OCR — **implemented**
   (`services/pipeline_verox.py`, GPU required, tested on Tesla T4)
2. Structured extraction using regex rules — **implemented** (CPU only)
3. Consistency validation (Pydantic) — **implemented**
4. Targeted VLM-OCR fallback for missing fields — **implemented**
   (GPU required)
5. Anti-hallucination guardrails — **implemented**
6. Results exposed via API and persisted to a database — **planned**

## Hardware requirements

The vision-language model (GLM-OCR) is served through vLLM and requires
a GPU to run at usable speed. Tested on an NVIDIA Tesla T4 (Kaggle).

Note on startup time: vLLM needs to load the model into GPU memory and
compile CUDA kernels on first launch (a few minutes). Once running,
each document is processed in a few seconds. For production, the
server should stay warm on a dedicated GPU instance (e.g. RunPod)
rather than being restarted per request.

## Tech stack

| Component | Status |
|---|---|
| GLM-OCR (vision-language model) | in use |
| vLLM (inference server) | in use |
| Python regex (extraction) | implemented |
| Pydantic (validation) | implemented |
| FastAPI (backend API) | planned |
| PostgreSQL / SQLite (persistence) | planned |

## Getting started

Install the dependencies:
```bash
!pip uninstall -y transformers -q
!pip install git+https://github.com/huggingface/transformers.git -q
!pip install -U vllm --pre --extra-index-url https://wheels.vllm.ai/nightly -q
!pip install -q pydantic rapidfuzz openai
```

Run the full pipeline end-to-end by connecting your own GLM-OCR
server (served via vLLM). See `services/pipeline_verox.py` for the
server startup and integration code — point it to your vLLM endpoint
(local GPU or a hosted instance such as RunPod) and process a delivery
note image directly.