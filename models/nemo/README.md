# **NVIDIA NeMo Benchmarking Module**

This module enables benchmarking of **NVIDIA NeMo** diarization models (specifically Sortformer architecture) using a containerized environment tailored for high-performance GPUs (Grace Blackwell / Hopper / Ampere).

## **Prerequisites**

1. **Docker** with NVIDIA Container Toolkit.  
2. **HuggingFace Token** (Read-only) with accepted licenses for:  
   * [nvidia/diar\_sortformer\_4spk-v1](https://huggingface.co/nvidia/diar_sortformer_4spk-v1)  
   * [nvidia/diar\_streaming\_sortformer\_4spk-v2](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2)  
   * [nvidia/diar\_streaming\_sortformer\_4spk-v2.1](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2.1)

## **1\. Building the Docker Image**

```

cd models/nemo
docker build -t benchmark-nemo .

```

*Base Image: nvcr.io/nvidia/pytorch:25.09-py3 (Supports Blackwell GB10/GB200)*

## **2\. Running the Benchmark**

### **🚀 Best Practice: Mount HuggingFace Cache**

To avoid re-downloading large NeMo models (\~200MB \- 1GB) on every run, mount your local HuggingFace cache directory.

### **Scenario A: Streaming Sortformer (v2) \- Default**

This model uses a sliding window approach. It is extremely fast (RTF \~0.006) and has constant memory usage regardless of file length.

```

docker run --gpus all --rm \
  -v "$(pwd)/data/ROG-Dialog/audio:/data/audio" \
  -v "$(pwd)/results/nemo_v2:/data/output" \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
  -e HOST_UID=$(id -u) \
  -e HOST_GID=$(id -g) \
  -e HF_TOKEN="YOUR_TOKEN" \
  benchmark-nemo \
  --input /data/audio \
  --output /data/output

```

### **Scenario B: Offline Sortformer (v1) \- Memory Intensive**

This model uses **Global Attention**. Memory usage grows quadratically ($O(T^2)$) with audio duration.

* **Warning:** Files longer than \~20-30 minutes may cause **OOM (Out Of Memory)** crashes even on 80GB+ GPUs.  
* **Safe Mode:** Use \--max-duration to skip files that are too long for your hardware.

```

docker run --gpus all --rm \
  -v "$(pwd)/data/ROG-Dialog/audio:/data/audio" \
  -v "$(pwd)/results/nemo_v1:/data/output" \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  benchmark-nemo \
  --input /data/audio \
  --output /data/output \
  --model nvidia/diar_sortformer_4spk-v1 \
  --max-duration 1900

```

*Note: The script saves metadata incrementally. If it crashes, simply run it again with a lower \--max-duration, and it will resume from where it left off.*

## **3\. Output**

The container generates:

1. **RTTM Files:** Diarization output in /data/output.  
2. **Metadata (benchmark\_metadata.json):** Contains RTF (Real Time Factor) and Peak VRAM usage.

**Example Metadata:**

```

{
    "model_name": "nvidia/diar_sortformer_4spk-v1",
    "run_info": { "gpu_name": "NVIDIA GB10" },
    "timings": {
        "overall_rtf": 0.035,
        "max_vram_peak_mb": 106867.6  // Offline models consume huge VRAM!
    },
    "files": [
        {
            "filename": "Long_File",
            "error": "Skipped: Duration Exceeds Safety Limit"
        }
    ]
}

```

## **Troubleshooting**

* **Docker Crash without Error:** This is usually the Linux OOM Killer terminating the container because the Offline model exhausted system RAM/VRAM. Use \--max-duration.   
* **ValueError: could not convert string to float**: Ensure you are using the updated run\_inference.py that handles NeMo batch output lists correctly.
