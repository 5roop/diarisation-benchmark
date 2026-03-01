# **PyAnnote Diarization Benchmarking Module**

This module enables benchmarking of **PyAnnote** diarization models using a containerized environment. It supports both local, open-weights models and PyAnnote's premium remote API models.

## **Prerequisites**

1. **Docker** with NVIDIA Container Toolkit (for local models).  
2. **Access Tokens** (depending on the model you use):  
   * **HuggingFace Token**: Required for local models like 3.1. You must accept the user conditions on HF for pyannote/speaker-diarization-3.1 and pyannote/segmentation-3.0.  
   * **PyAnnote API Key**: Required *only* if using the precision-2 cloud model. You can get free credits by creating an account on the [pyannoteAI dashboard](https://dashboard.pyannote.ai/).

## **1\. Building the Docker Image**

```

cd models/pyannote
docker build -t benchmark-pyannote .

```

## **2\. Running Local Models (Default)**

Local models load heavy weights into your GPU. **Best Practice:** Mount your local HuggingFace cache directory so you don't re-download the \~2GB models on every run.

**Supported Local Models:**

* pyannote/speaker-diarization-3.1 (Default)  
* pyannote/speaker-diarization-3.0  
* pyannote/speaker-diarization-community-1 (Unrestricted access)

**Example Run (PyAnnote 3.1):**

```

docker run --gpus all --rm \
  -v "$(pwd)/data/ROG-Dialog/audio:/data/audio" \
  -v "$(pwd)/results/pyannote_3_1:/data/output" \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
  -e HOST_UID=$(id -u) \
  -e HOST_GID=$(id -g) \
  -e HF_TOKEN="YOUR_HUGGINGFACE_TOKEN" \
  benchmark-pyannote \
  --input /data/audio \
  --output /data/output \
  --model pyannote/speaker-diarization-3.1

```

## **3\. Running Remote API Models (Precision-2)**

PyAnnote offers a highly accurate, cloud-based model called pyannote/speaker-diarization-precision-2. The Python package handles the API communication seamlessly.

To run this, pass your **PyAnnote API Key** into the HF\_TOKEN environment variable.

```

docker run --rm \
  -v "$(pwd)/data/ROG-Dialog/audio:/data/audio" \
  -v "$(pwd)/results/pyannote_precision_2:/data/output" \
  -e HOST_UID=$(id -u) \
  -e HOST_GID=$(id -g) \
  -e HF_TOKEN="YOUR_PYANNOTE_API_KEY" \
  benchmark-pyannote \
  --input /data/audio \
  --output /data/output \
  --model pyannote/speaker-diarization-precision-2

```

### **⚠️ Important Notes for the Precision-2 API:**

* **GPU Not Required:** Since processing happens on PyAnnote servers, you do not need the \--gpus all flag.  
* **0.0 MB Peak VRAM:** In your benchmark reports, the VRAM usage will correctly show as 0.0 MB because the local GPU is bypassed.  
* **Polling Warnings:** During execution, you will see the following warning:  
  *You are using periodic polling to retrieve results. If you are running in production, we highly recommend to setup a webhook server...*  
  This is completely normal and expected for this benchmarking script. It just means the script is asking the server "Are you done yet?" every few seconds until the RTTM is generated.

## **4\. Output**

The container generates:

1. **RTTM Files:** Standard output format for diarization boundaries.  
2. **Metadata (benchmark\_metadata.json):** Contains RTF (Real Time Factor) and Peak VRAM usage for the final report.
