# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-01

### Added

- **Automated Dataset Management**: Scripts for downloading ROG-Dialog dataset and generating gold standard RTTM from TRS format
  - `prepare_data.sh`: Dataset download and setup automation
  - `convert_trs_to_rttm.py`: TRS to RTTM format conversion
  - Maintains reference `rog-dialog.rttm` for comparison

- **Inference Pipeline**: Complete ML model evaluation framework
  - **PyAnnote Models** (`models/pyannote/`): Inference runner for pyannote-compatible speaker diarization models
    - Support for legacy 3.1, community-1, and precision-2 variants
    - Docker containerization for reproducible environments
  - **NVIDIA Softformer Models** (`models/nemo/`): Inference runner for diar_sortformer family
    - Support for offline (v1) and streaming (v2, v2.1) variants
    - Optimized for high-performance GPUs (Grace Blackwell/Hopper/Ampere)

- **Evaluation & Reporting Module** (`evaluation/`)
  - `score.py`: Quick CLI tool for DER calculation against gold standard
    - Supports configurable collar values and margin settings
  - `generate_report.py`: Comprehensive benchmark report generation with visualizations
    - Multi-metric evaluation: DER (Diarization Error Rate), Purity, Coverage
    - Dataset-specific errata handling via UEM (Universal Evaluation Maps)
    - Automated processing of all model results
  - `DATASET_ERRATA.json`: Configuration for handling transcription errors in dataset

- **Benchmark Results & Reports**
  - Multiple model evaluations across ROG-Dialog dataset
  - Result collections: pyannote_3_1, pyannote_community_1, pyannote_precision_2, diar_sortformer variants
  - Generated benchmark reports with comparative analysis

- **Documentation**
  - Module-specific READMEs with usage instructions and Docker commands
  - Markdown reports with visualizations and detailed metrics
  - Root reference documentation on dataset, models, and evaluation methodology
