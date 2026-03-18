# diarisation-benchmark
First steps in setting up a diarisation benchmark for Slovenian and related languages

## Dataset

We will start with the open dataset ROG-Dialog http://hdl.handle.net/11356/2073. The audio is to be taken from the repository, while the rttm format is available in this repository for simplicity (original repository contains XML Exmaralda files that can be investigated if needed, editor is this: https://exmaralda.org/en/).

## Models

Models to be evaluated in the first iteration are
- pyannote (legacy 3.1, community-1, precision-2, or any others looking promising) https://huggingface.co/pyannote
- NVIDIA softformer https://huggingface.co/nvidia/diar_sortformer_4spk-v1
- NVIDIA NeMo models?
- SpeechBrain models?
- any other models identified as promising
- feel free to spend a few EUR (and bill us for these) on API-based diarisers (precision-2 etc.), if they perform significantly better, we are happy to use these as well for some data

## Evaluation

While all model outputs are to be logged for future evaluation runs, the first iteration should report
- diarisation error rate (DER) pyannote.metrics.diarization.DiarizationErrorRate
- processing speed

We are very open to additional metrics as well.



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
  --gold /data/rog/ref_rttm/gold_standard.rttm \
  --results_dir /data/results \
  --metadata /data/rog/docs/ROG-Dia-meta-speeches.tsv \
  --output /data/reports/ROG-Dia_Final_Report
```
