# diarisation-benchmark
First steps in setting up a diarisation benchmark for Slovenian and related languages

## Dataset

We currently support three datasets:

- **ROG-Dialog** (primary benchmark)
  - official source: http://hdl.handle.net/11356/2073
  - use `prepare_data_rog_dialog.sh` to download/unpack/reorganize and generate `data/ROG-Dialog/ref_rttm/*.rttm`
  - converter: `rog_dialog_data_process.py` (merge/min filtering, optional `.pog` vs `.std` selection)

- **ROG Art** (Training corpus of spoken Slovenian ROG 1.1)
  - official source: https://www.clarin.si/repository/xmlui/handle/11356/2062
  - use `prepare_data_rog_art.sh` to download/unpack/reorganize and generate `data/ROG-Art/ref_rttm/*.rttm`
  - converter: `rog_art_data_process.py` (multi-speaker subset from `ROG-speeches.tsv`, merge/min filtering, `.pog`/`.std` preference)
  - this benchmark uses only multi-speaker recordings as filtered by `SPK-IDsUTTS`

- **CHILDES Croatian Corpus of Preschool Child Language (CCPCL)**
  - source: requires registration/login via https://talkbank.org/childes/access/Slavic/Croatian/CCPCL.html
  - download archive manually to `data/raw/CCPCL.zip`, then run `./prepare_data_ccpcl.sh`
  - `prepare_data_ccpcl.sh` extracts to `data/raw/CCPCL`, validates `.wav` availability and optionally runs `ccpcl_data_process.py`
  - `ccpcl_data_process.py` reads `data/raw/CCPCL/CCPCL/*.cha`, creates `data/CHILDES-CCPCL/ref_rttm/ccpcl_gold_standard.rttm` with same merge/min merging logic

## Models

Explicit supported model names:

- nvidia/diar_sortformer_4spk-v1
- nvidia/diar_streaming_sortformer_4spk-v2
- nvidia/diar_streaming_sortformer_4spk-v2.1
- pyannote/speaker-diarization-3.1
- pyannote/speaker-diarization-community-1
- pyannote/speaker-diarization-precision-2
- Revai/reverb-diarization-v2

These entries are loaded from `results/<model_folder>/benchmark_metadata.json` (the `model_name` property inside each file).

Planned/in development support (WIP):

- BUT-FIT diaryzen-wavlm-large-s80-md: https://huggingface.co/BUT-FIT/diarizen-wavlm-large-s80-md


## Evaluation

Evaluation is run through the benchmark report generator and uses model outputs versus reference RTTM.
Check `reports/ROG-Dia_rog-auto-gold-rttm_Report/ROG_Dia_Benchmark_Report.md` for how the current evaluation is done.

The report includes:
- diarisation error rate (DER), false alarm, missed speech and speaker confusion
- purity / coverage and per-talk evaluation
- model-specific latency and real-time factor
- summarization of all models from configured `results/*/benchmark_metadata.json`

The first iteration uses the existing reference RTTM outputs and computes diarisations with DER as primary metric.

Future metric extensions may include JER, boundary F-score, cluster consistency, and more.
