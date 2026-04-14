import argparse
import csv
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

# --- KONFIGURACIJA ---
DATASET_NAME = "ROG-Art"
DEFAULT_MERGE_THRESHOLD = 1.0  # Sekunde
DEFAULT_MIN_DURATION = 0.1  # Sekunde
DEFAULT_PRIORITIZE_POG = False

REPO_ROOT = Path(__file__).resolve().parent
RAW_ROOT = REPO_ROOT / "data/raw/data/ROG-Art/ROG"
SOURCE_PATHS = {
    "audio": RAW_ROOT / "ROG-Art" / "WAV",
    "trs": RAW_ROOT / "ROG-Art" / "TRS",
    "exb": RAW_ROOT / "ROG-Art" / "EXB",
    "exs": RAW_ROOT / "ROG-Art" / "EXS",
    "metadata": RAW_ROOT / "METADATA",
}

DEST_BASE = REPO_ROOT / "data" / DATASET_NAME
DEST_DIRS = {
    "audio": DEST_BASE / "audio",
    "docs": DEST_BASE / "docs",
    "trs": DEST_BASE / "annotations" / "trs",
    "exb": DEST_BASE / "annotations" / "exb",
    "exs": DEST_BASE / "annotations" / "exs",
    "ref_rttm": DEST_BASE / "ref_rttm",
}


def merge_segments_linear(segments, gap_threshold):
    if not segments:
        return []

    segments.sort(key=lambda x: x["start"])
    merged = []
    current = segments[0]

    for next_seg in segments[1:]:
        if next_seg["speaker"] == current["speaker"]:
            gap = next_seg["start"] - current["end"]
            if gap <= gap_threshold:
                current["end"] = max(current["end"], next_seg["end"])
                continue

        merged.append(current)
        current = next_seg

    merged.append(current)
    return merged


def parse_trs_to_rttm(trs_path, output_file, merge_threshold, min_duration):
    try:
        tree = ET.parse(trs_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Warning: napaka pri parsiranju {trs_path}: {e}")
        return 0

    filename = Path(trs_path).stem
    file_id = filename.replace("-std", "").replace("-pog", "")

    speaker_map = {}
    for spk in root.findall(".//Speaker"):
        spk_id = spk.get("id")
        spk_name = spk.get("name")
        if spk_id and spk_name:
            speaker_map[spk_id] = spk_name

    all_raw_segments = []
    for turn in root.findall(".//Turn"):
        start_time = float(turn.get("startTime", 0))
        end_time = float(turn.get("endTime", 0))
        spk_refs = turn.get("speaker")
        if not spk_refs:
            continue

        for spk_ref in spk_refs.split():
            real_name = speaker_map.get(spk_ref, spk_ref)
            all_raw_segments.append({"start": start_time, "end": end_time, "speaker": real_name})

    smooth_segments = merge_segments_linear(all_raw_segments, merge_threshold)

    count = 0
    for seg in smooth_segments:
        duration = seg["end"] - seg["start"]
        if duration < min_duration:
            continue
        line = (
            f"SPEAKER {file_id} 1 {seg['start']:.3f} {duration:.3f} <NA> <NA> "
            f"{seg['speaker']} <NA> <NA>"
        )
        output_file.write(line + "\n")
        count += 1

    return count


def find_multi_speaker_recordings(metadata_file: Path):
    if not metadata_file.exists():
        print(f"Metadata ni najden: {metadata_file}")
        return set()

    multi = set()
    with metadata_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            text_id = row.get("TEXT-ID", "").strip()
            spk_ids = row.get("SPK-IDsUTTS", "").strip()
            if not text_id or not text_id.startswith("Rog-Art-"):
                continue

            parts = [p for p in spk_ids.replace(",", " ").split() if p]
            if len(parts) >= 2:
                multi.add(text_id)

    return multi


def copy_files(src_dir: Path, dst_dir: Path, pattern="*"):
    if not src_dir.exists():
        return 0
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in src_dir.glob(pattern):
        if path.is_file():
            shutil.copy2(path, dst_dir / path.name)
            copied += 1
    return copied


def reorganize_dataset(multi_speaker_ids: set):
    print(f"=== 1. Ustvarjam ciljno strukturo: data/{DATASET_NAME} ===")
    for d in DEST_DIRS.values():
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    # Audio
    n_audio = 0
    audio_src = SOURCE_PATHS["audio"]
    if audio_src.exists():
        for wav_file in audio_src.glob("*.wav"):
            base = wav_file.stem
            if base in multi_speaker_ids:
                shutil.copy2(wav_file, DEST_DIRS["audio"] / wav_file.name)
                n_audio += 1
    print(f"Kopiranih WAV (multi-govorniki): {n_audio}")

    # Annotations
    n_trs = 0
    n_exb = 0
    n_exs = 0

    for trs_file in SOURCE_PATHS["trs"].glob("*.trs"):
        base = trs_file.stem.replace("-std", "").replace("-pog", "")
        if base in multi_speaker_ids:
            shutil.copy2(trs_file, DEST_DIRS["trs"] / trs_file.name)
            n_trs += 1

    for exb_file in SOURCE_PATHS["exb"].glob("*.exb"):
        base = exb_file.stem
        if base in multi_speaker_ids:
            shutil.copy2(exb_file, DEST_DIRS["exb"] / exb_file.name)
            n_exb += 1

    for exs_file in SOURCE_PATHS["exs"].glob("*.exs"):
        base = exs_file.stem.replace("_s", "")
        if base in multi_speaker_ids:
            shutil.copy2(exs_file, DEST_DIRS["exs"] / exs_file.name)
            n_exs += 1

    print(f"Kopiranih TRS: {n_trs}, EXB: {n_exb}, EXS: {n_exs}")

    # Dokumentacija
    docs_src = SOURCE_PATHS["metadata"]
    if docs_src.exists():
        copied_docs = 0
        for p in docs_src.glob("**/*"):
            if p.is_file():
                rel = p.relative_to(docs_src)
                dst = DEST_DIRS["docs"] / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dst)
                copied_docs += 1
        print(f"Kopiranih dokumentov: {copied_docs}")


def generate_gold_rttm(merge_threshold, min_duration, prioritize_pog, output_filename):
    trs_dir = DEST_DIRS["trs"]
    if not trs_dir.exists():
        print(f"TRS mapo ni najdena: {trs_dir}")
        return

    all_trs = sorted(trs_dir.glob("*.trs"))
    if not all_trs:
        print("Ni TRS datotek za obdelavo.")
        return

    file_groups = {}
    for f in all_trs:
        base = f.stem.replace("-std", "").replace("-pog", "")
        file_groups.setdefault(base, []).append(f)

    final_name = output_filename if output_filename.endswith(".rttm") else f"{output_filename}.rttm"
    out_path = DEST_DIRS["ref_rttm"] / final_name

    with out_path.open("w", encoding="utf-8") as out_f:
        out_f.write(f"; Generated with merge_threshold={merge_threshold}s, min_duration={min_duration}s, prior_pog={prioritize_pog}, output_filename={final_name}\n")

        total_segments = 0
        for base_id, files in sorted(file_groups.items()):
            std_files = [f for f in files if "-std" in f.name]
            pog_files = [f for f in files if "-pog" in f.name]

            selected = None
            if prioritize_pog:
                selected = pog_files[0] if pog_files else (std_files[0] if std_files else files[0])
            else:
                selected = std_files[0] if std_files else (pog_files[0] if pog_files else files[0])

            chosen_name = selected.name if selected else "(none)"
            print(f"Processing {base_id} -> {chosen_name}")
            if selected:
                total_segments += parse_trs_to_rttm(selected, out_f, merge_threshold, min_duration)

    print(f"Gold RTTM written: {out_path}")


def is_dataset_organized(multi_speaker_ids: set):
    # Check whether core files for multi-speaker entries already exist.
    audio_dir = DEST_DIRS["audio"]
    trs_dir = DEST_DIRS["trs"]

    if not audio_dir.exists() or not trs_dir.exists():
        return False

    for item in multi_speaker_ids:
        audio_file = audio_dir / f"{item}.wav"
        has_trs = (trs_dir / f"{item}-std.trs").exists() or (trs_dir / f"{item}-pog.trs").exists()
        if not audio_file.exists() or not has_trs:
            return False

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Prepare ROG-Art data subset (multi-speaker) and generate filtered RTTM gold standard",
        epilog="Example: python3 rog_art_data_process.py --merge_threshold 1.0 --min_duration 0.1 "
               "--prioritize_pog false --output_filename myconfig --force_reorganize"
    )
    parser.add_argument(
        "--merge_threshold",
        type=float,
        default=DEFAULT_MERGE_THRESHOLD,
        help="(float) Threshold (seconds) for merging adjacent same-speaker segments. Default: %(default)s."
    )
    parser.add_argument(
        "--min_duration",
        type=float,
        default=DEFAULT_MIN_DURATION,
        help="(float) Minimum segment duration (seconds) to keep in RTTM. Default: %(default)s."
    )
    parser.add_argument(
        "--prioritize_pog",
        type=lambda x: x.lower() in ["1", "true", "yes"],
        default=DEFAULT_PRIORITIZE_POG,
        help="(bool) Use .pog transcripts first if available; otherwise use .std. Accepts true/false. Default: %(default)s."
    )
    parser.add_argument(
        "--force_reorganize",
        action="store_true",
        default=False,
        help="(flag) Force reorganization of the dataset even if it appears already organized."
    )
    parser.add_argument(
        "--output_filename",
        type=str,
        required=True,
        help="(string) Output RTTM filename (with or without .rttm extension). Required."
    )
    args = parser.parse_args()

    metadata_file = SOURCE_PATHS["metadata"] / "ROG-speeches.tsv"
    if not metadata_file.exists():
        fallback_metadata = DEST_DIRS["docs"] / "ROG-speeches.tsv"
        if fallback_metadata.exists():
            metadata_file = fallback_metadata
            print(f"Metadata izvor ni najden, preklop na reorganizirano pot: {metadata_file}")

    print("=== Identifikacija posnetkov z 2+ govorcev ===")
    multi_speaker = find_multi_speaker_recordings(metadata_file)
    print(f"Najdenih posnetkov z vsaj 2 govorci (Rog-Art): {len(multi_speaker)}")
    if multi_speaker:
        for r in sorted(multi_speaker):
            print(" -", r)

    if args.force_reorganize or not is_dataset_organized(multi_speaker):
        print("Dataset se reorganizira.")
        reorganize_dataset(multi_speaker)
    else:
        print("Dataset že reorganiziran. Preskočim reorganization.")

    generate_gold_rttm(args.merge_threshold, args.min_duration, args.prioritize_pog, args.output_filename)


if __name__ == "__main__":
    main()
