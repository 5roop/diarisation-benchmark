"""
Diarisation Benchmark - PyAnnote Inference Runner
===================================================
Project: diarisation-benchmark
Description: Runs inference for pyannote-compatible speaker diarization models
             on the ROG-Dialog dataset and outputs results in RTTM format.

Author: Tomaž Savodnik
Date: March 2026
"""

import os
import argparse
import torch
import glob
import time
import json
import platform
import datetime
import soundfile as sf
from pathlib import Path
from pyannote.audio import Pipeline
def fix_permissions(path, uid, gid):
    """Rekurzivno spremeni lastništvo datotek in map."""
    print(f"Fixing permissions for {path} -> {uid}:{gid}...", flush=True)
    try:
        # Spremeni mapo samo
        os.chown(path, uid, gid)
        # Spremeni vsebino
        for root, dirs, files in os.walk(path):
            for d in dirs:
                os.chown(os.path.join(root, d), uid, gid)
            for f in files:
                os.chown(os.path.join(root, f), uid, gid)
        print("Permissions fixed.", flush=True)
    except Exception as e:
        print(f"WARNING: Could not fix permissions: {e}", flush=True)
        
def log(msg):
    """Izpis s takojšnjim flush-om."""
    print(msg, flush=True)

def get_system_info(device):
    info = {
        "timestamp": datetime.datetime.now().isoformat(),
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "system": platform.system(),
        "processor": platform.processor(),
        "device_type": device,
    }

    if device == "cuda":
        try:
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_count"] = torch.cuda.device_count()
            # Total VRAM v GB
            info["gpu_total_vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)
            info["cuda_version"] = torch.version.cuda
        except Exception as e:
            info["gpu_error"] = str(e)
    else:
        info["gpu_name"] = "N/A"
    
    return info

def get_peak_memory_mb():
    """Vrne največjo porabo GPU pomnilnika v MB od zadnjega reseta."""
    if torch.cuda.is_available():
        return torch.cuda.max_memory_allocated() / (1024 * 1024)
    return 0.0

def get_audio_duration(file_path):
    try:
        with sf.SoundFile(file_path) as f:
            return f.frames / f.samplerate
    except Exception as e:
        log(f"Warning: Could not get duration via soundfile for {file_path}: {e}")
        return 0.0

def run_inference(input_dir, output_dir, hf_token, device="cuda", model_name="pyannote/speaker-diarization-3.1"):
    log(f"--- STARTING BENCHMARK ---")
    log(f"Target Model: {model_name}")
    
    if torch.cuda.is_available():
        log(f"CUDA is available! Found {torch.cuda.device_count()} devices.")
        log(f"Current device: {torch.cuda.get_device_name(0)}")
        # Resetiramo statistiko na začetku
        torch.cuda.reset_peak_memory_stats()
    else:
        log("!!! WARNING: CUDA IS NOT AVAILABLE !!!")
        if device == "cuda":
            device = "cpu"

    sys_info = get_system_info(device)
    log(f"Run config: {sys_info.get('gpu_name', 'CPU')}")

    # 1. Pipeline Loading
    load_start = time.time()
    log(f"Loading PyAnnote pipeline: {model_name}...")
    
    try:
        pipeline = Pipeline.from_pretrained(
            model_name,
            token=hf_token 
        )
    except Exception as e:
        log(f"ERROR loading pipeline '{model_name}': {e}")
        return

    pipeline.to(torch.device(device))
    load_time = time.time() - load_start
    
    # Izmerimo porabo samo za nalaganje modela
    model_vram_mb = get_peak_memory_mb()
    log(f"Model loaded in {load_time:.2f}s (Base VRAM usage: {model_vram_mb:.1f} MB)")

    os.makedirs(output_dir, exist_ok=True)

    # 2. Files
    audio_files = glob.glob(os.path.join(input_dir, "*.wav"))
    audio_files.sort()
    log(f"Found {len(audio_files)} audio files in {input_dir}")

    benchmark_stats = {
        "model_name": model_name,
        "run_info": sys_info,
        "timings": {
            "model_load_time_s": load_time,
            "total_processing_time_s": 0.0,
            "total_audio_duration_s": 0.0,
            "overall_rtf": 0.0,
            "max_vram_peak_mb": 0.0  # Globalni maximum
        },
        "files": []
    }

    total_proc_time = 0.0
    total_audio_dur = 0.0
    global_max_vram = model_vram_mb

    # 3. Inference Loop
    for i, audio_path in enumerate(audio_files):
        filename = Path(audio_path).stem
        output_rttm_path = os.path.join(output_dir, f"{filename}.rttm")
        
        # Resetiramo števec pomnilnika pred vsako datoteko, 
        # da vidimo, koliko specifično ta datoteka porabi.
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()

        if os.path.exists(output_rttm_path):
            log(f"[{i+1}/{len(audio_files)}] Skipping {filename} (already exists)")
            continue

        log(f"[{i+1}/{len(audio_files)}] Processing {filename}...")
        
        audio_dur = get_audio_duration(audio_path)
        file_start_time = time.time()
        
        try:
            # --- INFERENCE ---
            result = pipeline(audio_path)
            
            # --- API ADAPTATION ---
            annotation = None
            if hasattr(result, "speaker_diarization"):
                annotation = result.speaker_diarization
            elif hasattr(result, "annotation"):
                annotation = result.annotation
            elif hasattr(result, "write_rttm"):
                annotation = result
            elif isinstance(result, tuple):
                 annotation = result[0]
            else:
                annotation = result

            proc_duration = time.time() - file_start_time
            rtf = proc_duration / audio_dur if audio_dur > 0 else 0
            
            # --- MERJENJE VRAM ---
            # Koliko je bil peak med procesiranjem te datoteke?
            current_peak_mb = get_peak_memory_mb()
            if current_peak_mb > global_max_vram:
                global_max_vram = current_peak_mb
            
            log(f"   -> Processed {audio_dur:.1f}s in {proc_duration:.1f}s (RTF: {rtf:.3f}, Peak VRAM: {current_peak_mb:.1f} MB)")

            total_proc_time += proc_duration
            total_audio_dur += audio_dur
            
            benchmark_stats["files"].append({
                "filename": filename,
                "audio_duration_s": audio_dur,
                "processing_time_s": proc_duration,
                "rtf": rtf,
                "peak_vram_mb": current_peak_mb
            })

            # Write RTTM
            if hasattr(annotation, "write_rttm"):
                 with open(output_rttm_path, "w") as f:
                    annotation.write_rttm(f)
            else:
                log(f"ERROR: Could not find write_rttm method on result object. Type: {type(result)}")
                continue

            # Normalize RTTM
            clean_lines = []
            with open(output_rttm_path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        parts[1] = filename
                        clean_lines.append(" ".join(parts))
            with open(output_rttm_path, "w") as f:
                f.write("\n".join(clean_lines) + "\n")

        except Exception as e:
            log(f"ERROR processing {filename}: {e}")
            import traceback
            traceback.print_exc()
            benchmark_stats["files"].append({
                "filename": filename,
                "error": str(e)
            })

    # Stats
    if total_audio_dur > 0:
        overall_rtf = total_proc_time / total_audio_dur
    else:
        overall_rtf = 0

    benchmark_stats["timings"]["total_processing_time_s"] = total_proc_time
    benchmark_stats["timings"]["total_audio_duration_s"] = total_audio_dur
    benchmark_stats["timings"]["overall_rtf"] = overall_rtf
    benchmark_stats["timings"]["max_vram_peak_mb"] = global_max_vram
    
    json_path = os.path.join(output_dir, "benchmark_metadata.json")
    with open(json_path, "w") as f:
        json.dump(benchmark_stats, f, indent=4)
       
    try:
        host_uid = int(os.environ.get("HOST_UID", 0))
        host_gid = int(os.environ.get("HOST_GID", 0))
        
        # Če sta nastavljena in nista root, popravimo
        if host_uid > 0:
            fix_permissions(output_dir, host_uid, host_gid)
            
    except ValueError:
        pass 
    log("Done!")
    log(f"Overall RTF: {overall_rtf:.3f}")
    log(f"Max VRAM Usage: {global_max_vram:.1f} MB")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--token", help="HuggingFace Token")
    parser.add_argument("--model", default="pyannote/speaker-diarization-3.1", help="HF Model ID")
    parser.add_argument("--cpu", action="store_true")
    
    args = parser.parse_args()
    
    token = args.token or os.environ.get("HF_TOKEN")
    if not token:
        log("ERROR: HF_TOKEN required.")
        exit(1)
        
    if args.cpu:
        device = "cpu"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
        
    run_inference(args.input, args.output, token, device, args.model)