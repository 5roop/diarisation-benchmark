"""
Diarisation Benchmark - NVIDIA Softformer Inference Runner
===========================================================
Project: diarisation-benchmark
Description: Runs inference for NVIDIA Softformer speaker diarization models
             (diar_sortformer_4spk variants) on the ROG-Dialog dataset and 
             outputs results in RTTM format. Supports both offline (v1) and 
             streaming (v2, v2.1) variants.

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
import logging
from pathlib import Path

# Utišamo NeMo loge
os.environ["NEMO_LOG_LEVEL"] = "ERROR"
logging.getLogger("nemo_logger").setLevel(logging.ERROR)

def log(msg):
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
            info["gpu_vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)
            info["cuda_version"] = torch.version.cuda
        except Exception as e:
            info["gpu_error"] = str(e)
    return info

def get_peak_memory_mb():
    if torch.cuda.is_available():
        return torch.cuda.max_memory_allocated() / (1024 * 1024)
    return 0.0

def get_audio_duration(file_path):
    try:
        with sf.SoundFile(file_path) as f:
            return f.frames / f.samplerate
    except Exception:
        return 0.0

def fix_permissions(path, uid, gid):
    try:
        os.chown(path, uid, gid)
        # Če je pot datoteka, spremenimo samo njo
        if os.path.isfile(path):
            return
        # Če je mapa, rekurzivno
        for root, dirs, files in os.walk(path):
            for d in dirs: os.chown(os.path.join(root, d), uid, gid)
            for f in files: os.chown(os.path.join(root, f), uid, gid)
    except: pass

def save_metadata(output_dir, stats):
    """Shrani metapodatke in popravi pravice."""
    json_path = os.path.join(output_dir, "benchmark_metadata.json")
    try:
        with open(json_path, "w") as f:
            json.dump(stats, f, indent=4)
        
        # Takoj popravimo pravice, da uporabnik lahko bere/piše tudi če crasha
        uid = int(os.environ.get("HOST_UID", 0))
        gid = int(os.environ.get("HOST_GID", 0))
        if uid > 0:
            fix_permissions(json_path, uid, gid)
    except Exception as e:
        log(f"WARNING: Failed to save metadata: {e}")

def run_inference(input_dir, output_dir, hf_token, device="cuda", model_name="nvidia/diar_streaming_sortformer_4spk-v2", max_duration=0):
    log(f"--- STARTING NEMO BENCHMARK ---")
    log(f"Model: {model_name}")
    if max_duration > 0:
        log(f"Safety Limit: Skipping files longer than {max_duration}s")

    if device == "cuda" and not torch.cuda.is_available():
        log("WARNING: CUDA not available, falling back to CPU")
        device = "cpu"

    # --- INITIALIZE STATS & RESUME LOGIC ---
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "benchmark_metadata.json")
    
    benchmark_stats = {
        "model_name": model_name,
        "run_info": get_system_info(device),
        "timings": {"model_load_time_s": 0.0, "max_vram_peak_mb": 0.0},
        "files": []
    }

    # Akumulatorji
    total_proc = 0.0
    total_audio = 0.0
    global_max_vram = 0.0
    processed_files = set()

    # Preveri, če že obstaja JSON za nadaljevanje (Resume)
    if os.path.exists(json_path):
        log("Found existing benchmark_metadata.json. Resuming...")
        try:
            with open(json_path, "r") as f:
                existing_stats = json.load(f)
                
            # Če je isti model, naložimo obstoječe rezultate
            if existing_stats.get("model_name") == model_name:
                benchmark_stats["files"] = existing_stats.get("files", [])
                
                # Rekonstrukcija globalnih števcev
                for fstat in benchmark_stats["files"]:
                    fname = fstat.get("filename")
                    if fname:
                        processed_files.add(fname)
                    
                    # Prištejemo samo uspešne teke k skupnim časom
                    if "error" not in fstat:
                        total_proc += fstat.get("processing_time_s", 0)
                        total_audio += fstat.get("audio_duration_s", 0)
                        vram = fstat.get("peak_vram_mb", 0)
                        if vram > global_max_vram: global_max_vram = vram
                
                log(f"Resumed {len(processed_files)} previously processed files.")
            else:
                log("Existing metadata is for a different model. Overwriting.")
        except Exception as e:
            log(f"Error reading existing metadata: {e}. Starting fresh.")

    # --- 1. NEMO IMPORT ---
    log("Importing NeMo...")
    try:
        import nemo.collections.asr as nemo_asr
        from nemo.collections.asr.models import SortformerEncLabelModel
    except ImportError as e:
        log(f"CRITICAL: NeMo not installed correctly. {e}")
        return

    # --- 2. MODEL LOADING ---
    load_start = time.time()
    log("Downloading/Loading Model...")
    
    try:
        model = SortformerEncLabelModel.from_pretrained(model_name=model_name)
    except Exception as e:
        log(f"ERROR loading model: {e}")
        return

    model.to(torch.device(device))
    model.eval()
    
    load_time = time.time() - load_start
    # Če smo nadaljevali, morda želimo ohraniti star load time ali pa povprečiti?
    # Najlažje je vzeti trenutnega, saj je svež.
    benchmark_stats["timings"]["model_load_time_s"] = load_time
    
    model_vram = get_peak_memory_mb()
    if model_vram > global_max_vram: global_max_vram = model_vram
    
    log(f"Model loaded in {load_time:.2f}s (Base VRAM: {model_vram:.1f} MB)")

    audio_files = sorted(glob.glob(os.path.join(input_dir, "*.wav")))
    log(f"Found {len(audio_files)} files.")

    # --- 3. INFERENCE LOOP ---
    for i, audio_path in enumerate(audio_files):
        filename = Path(audio_path).stem
        out_path = os.path.join(output_dir, f"{filename}.rttm")
        
        # --- RESUME CHECK ---
        # Če je datoteka že v JSON-u (uspešno ali z napako), jo preskočimo
        # Razen če želimo ponovno poskusiti tiste z errorjem? Zaenkrat preskočimo vse zabeležene.
        if filename in processed_files:
            log(f"[{i+1}/{len(audio_files)}] Skipping {filename} (found in metadata)")
            continue

        if device == "cuda": torch.cuda.reset_peak_memory_stats()

        # --- PREVERJANJE DOLŽINE (OOM GUARD) ---
        dur = get_audio_duration(audio_path)
        if max_duration > 0 and dur > max_duration:
            log(f"[{i+1}/{len(audio_files)}] SKIPPING {filename}: Duration {dur:.1f}s > limit {max_duration}s")
            
            # Zabeležimo skip v JSON, da ga naslednjič ne preverjamo spet
            file_stat = {
                "filename": filename,
                "audio_duration_s": dur,
                "error": "Skipped: Duration Exceeds Safety Limit"
            }
            benchmark_stats["files"].append(file_stat)
            processed_files.add(filename)
            save_metadata(output_dir, benchmark_stats) # SPROTNO SHRANJEVANJE
            continue

        log(f"[{i+1}/{len(audio_files)}] Processing {filename}...")
        start = time.time()

        try:
            with torch.no_grad():
                batch_predictions = model.diarize(audio=[audio_path], batch_size=1)
                predictions = batch_predictions[0] if batch_predictions else []

            proc_time = time.time() - start
            rtf = proc_time / dur if dur > 0 else 0
            
            peak_vram = get_peak_memory_mb()
            if peak_vram > global_max_vram: global_max_vram = peak_vram
            
            log(f"   -> Processed {dur:.1f}s in {proc_time:.1f}s (RTF: {rtf:.3f}, VRAM: {peak_vram:.1f} MB)")

            # --- ZAPIS RTTM ---
            segment_count = 0
            with open(out_path, "w") as f:
                for segment in predictions:
                    t_start, t_end, label = 0.0, 0.0, ""
                    
                    if isinstance(segment, str):
                        parts = segment.split()
                        if len(parts) >= 3:
                            try:
                                t_start, t_end, label = float(parts[0]), float(parts[1]), parts[2]
                            except ValueError: continue 
                        else: continue
                    elif isinstance(segment, (tuple, list)) and len(segment) >= 3:
                        t_start, t_end, label = float(segment[0]), float(segment[1]), str(segment[2])
                    else: continue

                    if label.isdigit(): label = f"speaker_{label}"
                    duration = t_end - t_start
                    f.write(f"SPEAKER {filename} 1 {t_start:.3f} {duration:.3f} <NA> <NA> {label} <NA> <NA>\n")
                    segment_count += 1
            
            if segment_count == 0:
                log(f"WARNING: No segments written for {filename}.")

            total_proc += proc_time
            total_audio += dur
            
            file_stat = {
                "filename": filename, "audio_duration_s": dur, 
                "processing_time_s": proc_time, "rtf": rtf, "peak_vram_mb": peak_vram
            }
            benchmark_stats["files"].append(file_stat)
            processed_files.add(filename)

        except torch.cuda.OutOfMemoryError:
            log(f"CRITICAL ERROR: OOM processing {filename}!")
            log(f"VRAM before crash: {get_peak_memory_mb():.1f} MB")
            torch.cuda.empty_cache() 
            
            benchmark_stats["files"].append({"filename": filename, "error": "OOM: CUDA Out Of Memory"})
            processed_files.add(filename)

        except Exception as e:
            log(f"ERROR processing {filename}: {e}")
            import traceback
            traceback.print_exc()
            benchmark_stats["files"].append({"filename": filename, "error": str(e)})
            processed_files.add(filename)

        # --- UPDATE GLOBALS & SAVE AFTER EACH FILE ---
        # Posodobimo globalne statistike
        overall_rtf = total_proc / total_audio if total_audio > 0 else 0
        benchmark_stats["timings"]["total_processing_time_s"] = total_proc
        benchmark_stats["timings"]["total_audio_duration_s"] = total_audio
        benchmark_stats["timings"]["overall_rtf"] = overall_rtf
        benchmark_stats["timings"]["max_vram_peak_mb"] = global_max_vram
        
        # Shrani JSON takoj!
        save_metadata(output_dir, benchmark_stats)

    # Final permission fix for directory
    try:
        uid = int(os.environ.get("HOST_UID", 0))
        gid = int(os.environ.get("HOST_GID", 0))
        if uid > 0: fix_permissions(output_dir, uid, gid)
    except: pass

    log(f"Done! Overall RTF: {overall_rtf:.3f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--token", help="HF Token")
    parser.add_argument("--model", default="nvidia/diar_streaming_sortformer_4spk-v2")
    parser.add_argument("--max-duration", type=float, default=0, help="Skip files longer than X seconds")
    args = parser.parse_args()
    
    if args.token:
        os.environ["HUGGING_FACE_HUB_TOKEN"] = args.token

    run_inference(args.input, args.output, args.token, model_name=args.model, max_duration=args.max_duration)