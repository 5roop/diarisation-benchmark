# **Diarization Evaluation & Reporting Module**

This module calculates metrics (DER, Purity, Coverage) and generates comprehensive benchmark reports. It natively supports **UEM (Universal Evaluation Maps)** via a JSON errata file to account for dataset transcription errors.

## **1\. Structure**

* DATASET\_ERRATA.json: Configuration file defining regions of audio that should be ignored during evaluation (e.g., if the Gold Standard stops transcribing before the audio ends).  
* generate\_report.py: Generates the full Markdown report with visualizations.  
* score.py: Quick CLI tool to get the score for a single model.

## **2\. Building the Docker Image**

```

cd evaluation
docker build -t benchmark-eval .

```

## **3\. Generating the Full Report**

The report generator automatically reads all directories in your results/ folder.

```

docker run --rm \
  -v "$(pwd)/data/ROG-Dialog:/data/rog" \
  -v "$(pwd)/results:/data/results" \
  -v "$(pwd)/reports:/data/reports" \
  -v "$(pwd)/evaluation/DATASET_ERRATA.json:/app/DATASET_ERRATA.json" \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  benchmark-eval \
  --gold /data/rog/ref_rttm/gold_standard.rttm \
  --results_dir /data/results \
  --metadata /data/rog/docs/ROG-Dia-meta-speeches.tsv \
  --output /data/reports/ROG-Dia_Final_Report

```

### Generate report on other "gold" rttm

Copy "gold" rttm (e.g. rog-dialog.rttm from root of this project) to path `data/ROG-Dialog/ref_rttm/your.rttm` and then start the generator by:

```
 
docker run --rm \
  -v "$(pwd)/data/ROG-Dialog:/data/rog" \
  -v "$(pwd)/results:/data/results" \
  -v "$(pwd)/reports:/data/reports" \
  -v "$(pwd)/evaluation/DATASET_ERRATA.json:/app/DATASET_ERRATA.json" \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  benchmark-eval \
  --gold /data/rog/ref_rttm/your.rttm \
  --results_dir /data/results \
  --metadata /data/rog/docs/ROG-Dia-meta-speeches.tsv \
  --output /data/reports/ROG-Dia_Your_Report

```

**Customizing Errata:**

If you find new errors in the dataset, simply edit evaluation/DATASET\_ERRATA.json on your host machine. Because we map it via \-v, the Docker container will immediately use your updated rules without requiring a rebuild.

## **4\. Quick Evaluation (score.py)**

If you just want the numbers for one model without generating the full report:

```

docker run --rm --entrypoint python \
  -v "$(pwd)/data/ROG-Dialog:/data/rog" \
  -v "$(pwd)/results/pyannote_gpu:/data/system" \
  -v "$(pwd)/evaluation/DATASET_ERRATA.json:/app/DATASET_ERRATA.json" \
  benchmark-eval \
  score.py \
  --gold /data/rog/ref_rttm/gold_standard.rttm \
  --system /data/system \
  --collar 0.25

```
