# VEROX-BL — Delivery Note Extraction Pipeline

> OCR and information-extraction pipeline for converting delivery note
> images into validated structured data.

VEROX-BL is a Document AI pipeline designed to extract structured
information from pharmaceutical delivery notes.

The system combines **GLM-OCR** for document transcription with
deterministic Python-based extraction and **Pydantic** validation.
When a required field cannot be reliably recovered, a targeted
VLM-OCR fallback is used.

## Status

**Proof of concept — extraction pipeline implemented and tested
end-to-end on real delivery notes.**

Current development and testing have been performed on an
**NVIDIA Tesla T4 (Kaggle)**.

---

## Architecture

VEROX-BL separates document reading, deterministic extraction, and
validation. This makes the extraction process easier to control,
debug, and optimize.

```text
                         ┌─────────────────────┐
                         │   Delivery Note     │
                         │        Image        │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      GLM-OCR        │
                         │   Vision-Language   │
                         │       Model         │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │     Raw OCR Text    │
                         └──────────┬──────────┘
                                    │
                                    ▼
                  ┌────────────────────────────────┐
                  │    Deterministic Extraction    │
                  │                                │
                  │  • Header                      │
                  │  • Supplier / Client           │
                  │  • Products                    │
                  │  • Amounts                     │
                  └───────────────┬────────────────┘
                                  │
                                  ▼
                         ┌─────────────────────┐
                         │     Normalization   │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      Pydantic       │
                         │      Validation     │
                         └──────────┬──────────┘
                                    │
                           ┌────────┴────────┐
                           │                 │
                         Valid          Missing /
                           │             Invalid
                           │                 │
                           │                 ▼
                           │        ┌─────────────────┐
                           │        │ Targeted        │
                           │        │ GLM-OCR         │
                           │        │ Fallback        │
                           │        └────────┬────────┘
                           │                 │
                           └────────┬────────┘
                                    ▼
                         ┌─────────────────────┐
                         │  Validated JSON     │
                         └─────────────────────┘
```

---

## What's Implemented

### Document processing

- GLM-OCR document transcription
- vLLM-based inference
- Header information extraction
- Supplier / client name extraction
- Product line extraction
- Amount and total extraction

### Data processing

- Number and date normalization
- Pydantic data modelling
- Field-level validation
- Cross-field consistency checks
- Targeted VLM-OCR fallback
- End-to-end pipeline orchestration

The CPU-side extraction and validation logic is separated from the
GPU-dependent VLM inference layer.

---

## Repository Structure

```text
verox-bl/
│
├── pipelines/
│   ├── __init__.py
│   ├── extraction_entete.py
│   ├── extraction_noms.py
│   ├── extraction_produits.py
│   ├── modele_bl.py
│   ├── normalisation.py
│   └── orchestration.py
│
├── services/
│   └── pipeline_verox.py
│
├── requirements.txt
├── .gitignore
└── README.md
```

## Example Output

The pipeline produces structured data such as:

```json
{
  "numero_bl": "BL123456",
  "date": "2026-07-15",
  "fournisseur": "Example Supplier",
  "client": "Example Pharmacy",
  "produits": [
    {
      "code": "123456",
      "designation": "Example Product",
      "quantite": 5
    }
  ],
  "total_ttc": 125.500
}
```

> The example is illustrative and does not contain real supplier,
> pharmacy, or customer data.

---

## Performance

The main performance bottleneck is the GLM-OCR inference stage.

Current experiments have been conducted on an NVIDIA Tesla T4.
Inference latency depends on document complexity, generation length,
and inference configuration.

The CPU-side extraction and validation stages execute in milliseconds
compared with the VLM inference stage.

Current optimization work focuses on:

- Reducing unnecessary VLM calls
- Using targeted fallback instead of full-document reprocessing
- Optimizing generation length
- Optimizing vLLM configuration
- Benchmarking different GPU environments

Formal performance results will be reported after evaluation on a
representative dataset.

---

## Installation

```bash
git clone https://github.com/mohamedayoubayadi-ui/verox-bl.git
cd verox-bl
pip install -r requirements.txt
```

GLM-OCR inference requires a compatible NVIDIA GPU and a running
vLLM server.

The integration is implemented in:

```text
services/pipeline_verox.py
```

---

## Usage

The main pipeline is orchestrated through:

```text
pipelines/orchestration.py
```

The GLM-OCR / vLLM integration is handled by:

```text
services/pipeline_verox.py
```

The pipeline takes a delivery note image and produces structured,
validated data.

---

## Results & Next Steps

The pipeline has been implemented and tested end-to-end on real
delivery notes using an NVIDIA Tesla T4.

Current work focuses on improving extraction reliability and reducing
VLM inference latency.

Planned improvements include:

- Evaluation on a representative dataset
- Field-level accuracy and latency benchmarks
- Reference-data validation
- FastAPI integration
- Database persistence
- Production deployment and monitoring

---

## Experiments

The pipeline was evaluated on a set of real delivery notes provided
during the internship.

Due to the confidential nature of the documents, the original
documents and extracted data are not included in this repository.

Experiments were conducted on an NVIDIA Tesla T4 GPU using Kaggle,
with a focus on extraction quality and inference latency.

| Experiment | Initial OCR | Targeted Fallback | Total |
|----------|------------:|------------------:|------:|
| BL 1     | 13.63 s     | 0.70 s            | 14.33 s |
| BL 2     | 10.47 s     | 0.45 s            | 10.92 s |
| BL 3     | 9.27 s      | 0.46 s            | 9.73 s |

The initial OCR pass is currently the main contributor to the overall
inference time. In comparison, the targeted fallback passes introduce
only a small additional latency.

These preliminary results indicate that further optimization should
primarily focus on the initial GLM-OCR inference stage.

---

## References

- [GLM-OCR](https://github.com/zai-org/GLM-OCR) — Multimodal OCR model used for document reading, text extraction, and targeted fallback extraction.
- [Pydantic](https://docs.pydantic.dev/) — Used for validating and structuring the extracted delivery note data.
- [OmniDocBench](https://github.com/opendatalab/OmniDocBench) — Benchmark for evaluating document parsing and OCR systems.

## License

This project is currently developed as an internship project.

A license will be added before public redistribution.