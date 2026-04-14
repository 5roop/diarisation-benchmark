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



# Peter : Running the pipeline through and through

1. Download the data:

`bash prepare_data.sh`

2. Run pyannote:
    1. Build the docker image:

    ```bash
    cd models/pyannote
    docker build -t benchmark-pyannote .
    cd ../..
    ```

    2. Run first model:

    ```bash
    sudo docker run --rm \
        -v "$(pwd)/data/ROG-Dialog/audio:/data/audio" \
        -v "$(pwd)/results/pyannote_3_1:/data/output" \
        -e HOST_UID=$(id -u) \
        -e HOST_GID=$(id -g) \
        -e HF_TOKEN="YOURTOKEN" \
        benchmark-pyannote \
        --input /data/audio \
        --output /data/output \
        --model pyannote/speaker-diarization-3.1
    ```

    This works, but on GPU2 there is no docker, and on my laptop, there is no GPU.

    Consequently, processing takes ages, with RTF = 2!


3. Nemo models:
   1. Build the docker image:

    ```bash
    cd models/nemo
    sudo docker build -t benchmark-nemo .
    cd ../..
    ```

    2. Run first model:

    ```bash
    sudo docker run --rm \
        -v "$(pwd)/data/ROG-Dialog/audio:/data/audio" \
        -v "$(pwd)/results/nemo_v2:/data/output" \
        -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
        -e HOST_UID=$(id -u) \
        -e HOST_GID=$(id -g) \
        -e HF_TOKEN="YOURTOKEN" \
        benchmark-nemo \
        --input /data/audio \
        --output /data/output
    ```

    This runs faster, with RTF of 0.1 cca.

4. Run the eval

```bash
cd evaluation
sudo docker build -t benchmark-eval .
cd ..

sudo docker run --rm \
  -v "$(pwd)/data/ROG-Dialog:/data/rog" \
  -v "$(pwd)/results:/data/results" \
  -v "$(pwd)/reports:/data/reports" \
  -v "$(pwd)/evaluation/DATASET_ERRATA.json:/app/DATASET_ERRATA.json" \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  benchmark-eval \
  --gold /data/rog/ref_rttm/gold_trimmed.rttm \
  --results_dir /data/results \
  --metadata /data/rog/docs/ROG-Dia-meta-speeches.tsv \
  --output /data/reports/ROG-Dia-Trim
```

# Ivan: Auto-trim silences from Gold intervals with Praat (Apr2026)

Human-annotated segment boundaries in the gold RTTM often include leading/trailing silence (annotators clicking a bit too early or too late). The `trim_gold_silences_rttm.py` module uses Praat's pitch and intensity analysis (via Parselmouth) to detect actual speech onset/offset and tighten those boundaries automatically. It can also split segments at long internal silences.

## What it does

- Loads each audio file and analyses segments using pitch detection + intensity relative to segment peak
- Trims segment edges to where speech actually starts/ends, with a configurable guard margin
- Optionally splits segments at internal silences (e.g. ≥500ms gaps within a single annotation)
- Drops segments that become too short after trimming (configurable threshold)
- Writes results incrementally per file (crash-safe — no data lost if it fails mid-run)

### Impact of Gold Standard Trimming on Evaluation Metrics

Trimming the gold standard consistently lowers DER across all models, driven almost entirely by reduced Miss rates — the original annotations include silence at segment edges that unfairly penalizes models for not predicting speech where there is none. FA increases slightly (smaller speech denominator), while Confusion stays stable since trimming doesn't affect speaker identity.

Example using the best-performing model (pyannote speaker-diarization-precision-2, collar=0.25):

| Metric   | Original Gold | Trimmed Gold |
| -------- | ------------- | ------------ |
| DER      | 20.25%        | **9.52%**    |
| Miss     | 17.40%        | **5.78%**    |
| FA       | **1.26%**     | 2.37%        |
| Conf     | **1.22%**     | 1.36%        |
| Purity   | **86.91%**    | 86.89%       |
| Coverage | **89.32%**    | 89.09%       |

The trimmed evaluation better reflects actual diarisation performance by removing measurement artifacts from imprecise annotation boundaries.

## Two ways to use it

### 1. Standalone CLI (trim an existing RTTM)

```bash
python trim_gold_silences_rttm.py \
    --rttm data/ROG-Dialog/ref_rttm/gold_standard.rttm \
    --audio-dir data/ROG-Dialog/audio \
    --output data/ROG-Dialog/ref_rttm/gold_trimmed.rttm \
    --trim-silence-within \
    --verbose
```

Run `python trim_gold_silences_rttm.py --help` for all options (pitch range, intensity threshold, guard margin, max trim, etc.).

### 2. Integrated in the TRS→RTTM pipeline (recommended)

`convert_trs_to_trim_rttm.py` imports the trimming module and runs the full pipeline: parse TRS → merge segments → trim with audio → write RTTM + optional EXB files. All settings are configured at the top of the script:

```python
ENABLE_TRIMMING = True       # set False to skip audio analysis
GENERATE_EXB = True          # generate EXB files for visual inspection
TRIM_PARAMS = TrimParams(
    intensity_drop_db=15.0,  # dB below segment peak = "silence"
    trim_silence_within=True,
    min_silence_dur=0.5,
    verbose=False,
    # ... other params with sensible defaults
)
```

```bash
python convert_trs_to_trim_rttm.py
```

Output filename is automatic: `gold_standard_trimmed_{int}db.rttm` when trimming is on, `gold_standard.rttm` when off. A `_metadata.txt` file with full parameters and statistics is written alongside.

### EXB output

When `GENERATE_EXB = True`, the script produces EXB files with `[Dia_gold_trim]` tiers that can be opened in EXMARaLDA Partitur Editor alongside the original transcription tiers for visual verification of trim quality.

### Note on file_id

TRS filenames (e.g. `ROG-Dia-GSO-P0005-std.trs`) are stripped of `-std`/`-pog` suffixes to derive the file ID (`ROG-Dia-GSO-P0005`). This must match the corresponding `.wav` and `.exb` filenames.