#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


def merge_segments_linear(segments, gap_threshold):
    if not segments:
        return []
    segments.sort(key=lambda x: x["start"])
    merged = []
    current = segments[0].copy()
    for nxt in segments[1:]:
        if nxt["speaker"] == current["speaker"] and nxt["start"] - current["end"] <= gap_threshold:
            current["end"] = max(current["end"], nxt["end"])
            continue
        merged.append(current)
        current = nxt.copy()
    merged.append(current)
    return merged


def parse_cha_file(cha_path):
    segments = []
    speaker_pattern = re.compile(r"^\*(?P<speaker>[^:]+):.*?(?P<times>\d+_\d+)")
    with cha_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith("*"):
                continue
            m = speaker_pattern.search(line)
            if not m:
                continue
            speaker = m.group("speaker").strip().replace(" ", "_")
            times = m.group("times")
            try:
                start_ms, end_ms = map(int, times.split("_"))
            except ValueError:
                continue
            start = start_ms / 1000.0
            end = end_ms / 1000.0
            if end <= start:
                continue
            segments.append({"start": start, "end": end, "speaker": speaker})
    return segments


def generate_rttm_from_cha(cha_dir, output_file, merge_threshold, min_duration):
    cha_dir = Path(cha_dir)
    if not cha_dir.exists() or not cha_dir.is_dir():
        raise SystemExit(f"CHA目录不存在: {cha_dir}")

    all_files = sorted(cha_dir.glob("*.cha"))
    if not all_files:
        raise SystemExit(f"No .cha files in {cha_dir}")

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_segments = 0
    with output_path.open("w", encoding="utf-8") as out:
        out.write(f"; Generated from CCPCL .cha source merge_threshold={merge_threshold} min_duration={min_duration}\n")
        for cha_file in all_files:
            base_id = cha_file.stem
            raw_segments = parse_cha_file(cha_file)
            smooth = merge_segments_linear(raw_segments, merge_threshold)
            for seg in smooth:
                duration = seg["end"] - seg["start"]
                if duration < min_duration:
                    continue
                line = f"SPEAKER {base_id} 1 {seg['start']:.3f} {duration:.3f} <NA> <NA> {seg['speaker']} <NA> <NA>"
                out.write(line + "\n")
                total_segments += 1

    print(f"Wrote RTTM to {output_path} with {total_segments} segments")


def main():
    parser = argparse.ArgumentParser(description="CCPCL CHA -> RTTM converter")
    parser.add_argument("--cha_dir", type=str, default="data/raw/CCPCL/CCPCL", help="Directory with .cha files")
    parser.add_argument("--output_file", type=str, default="data/CHILDES-CCPCL/ref_rttm/ccpcl_gold_standard.rttm")
    parser.add_argument("--merge_threshold", type=float, default=1.0)
    parser.add_argument("--min_duration", type=float, default=0.1)
    args = parser.parse_args()

    generate_rttm_from_cha(args.cha_dir, args.output_file, args.merge_threshold, args.min_duration)


if __name__ == "__main__":
    main()
