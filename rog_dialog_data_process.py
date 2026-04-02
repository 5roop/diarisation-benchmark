import argparse
import os
import xml.etree.ElementTree as ET
from pathlib import Path

# --- KONFIGURACIJA BENCHMARKA ---
DEFAULT_MERGE_THRESHOLD = 1.0   # Sekunde. Če je tišina < 1.0s, združi.
DEFAULT_MIN_DURATION = 0.1      # Sekunde. Ignoriraj krajše segmente (šumi/kliki).
DEFAULT_PRIORITIZE_POG = False

# Logika: Linearno združevanje (Linear Merging)
# To pomeni, da združujemo segmente istega govorca, če je tišina med njimi manjša od praga,
# RAZEN če vmes spregovori drug govorec (turn-taking).
MERGE_THRESHOLD = 1.0   # Sekunde. Če je tišina < 1.0s, združi.
MIN_DURATION = 0.1      # Sekunde. Ignoriraj krajše segmente (šumi/kliki).

# --- IZBIRA VIRA ---
# Ali naj ima prednost pogovorni zapis (.pog) ali standardizirani (.std)?
# True = Prioriteta POG (morda več segmentov, vključuje mašila)
# False = Prioriteta STD (bolj čisti stavki, morda manj segmentov)
PRIORITIZE_POG = False 

def merge_segments_linear(segments, gap_threshold):
    """
    Linearno združevanje: Združi sosednje segmente istega govorca,
    če vmes ni drugega govorca in je pavza krajša od gap_threshold.
    """
    if not segments:
        return []

    # Sortiramo strogo po času
    segments.sort(key=lambda x: x['start'])
    
    merged = []
    current_seg = segments[0]
    
    for next_seg in segments[1:]:
        # 1. Isti govorec?
        if next_seg['speaker'] == current_seg['speaker']:
            gap = next_seg['start'] - current_seg['end']
            
            # 2. Ali je luknja dovolj majhna?
            if gap <= gap_threshold:
                # Združi (podaljšaj trenutnega)
                current_seg['end'] = max(current_seg['end'], next_seg['end'])
                continue
        
        # Če ne združimo (drug govorec ali prevelika luknja), shranimo.
        merged.append(current_seg)
        current_seg = next_seg
    
    merged.append(current_seg)
    return merged

def parse_trs_to_rttm(trs_path, output_file, merge_threshold, min_duration):
    try:
        tree = ET.parse(trs_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error parsing {trs_path}: {e}")
        return 0

    filename = Path(trs_path).stem
    # Odstranimo končnice, da dobimo čisti file_id
    file_id = filename.replace("-std", "").replace("-pog", "")
    
    # Mapiranje ID-jev govorcev (spk1 -> Ime)
    speaker_map = {}
    for spk in root.findall(".//Speaker"):
        spk_id = spk.get("id")
        spk_name = spk.get("name")
        if spk_id and spk_name:
            speaker_map[spk_id] = spk_name

    # 1. Branje surovih segmentov
    all_raw_segments = []
    turns = root.findall(".//Turn")
    
    for turn in turns:
        start_time = float(turn.get("startTime", 0))
        end_time = float(turn.get("endTime", 0))
        
        spk_refs = turn.get("speaker")
        if not spk_refs:
            continue
            
        for spk_ref in spk_refs.split(" "):
            if spk_ref in speaker_map:
                real_name = speaker_map[spk_ref]
                all_raw_segments.append({
                    'start': start_time,
                    'end': end_time,
                    'speaker': real_name
                })

    # 2. Uporaba definirane logike glajenja
    smooth_segments = merge_segments_linear(all_raw_segments, merge_threshold)
    
    # 3. Zapis
    count = 0
    for seg in smooth_segments:
        duration = seg['end'] - seg['start']
        
        if duration < min_duration:
            continue
            
        # RTTM Format: SPEAKER file_id 1 start duration <NA> <NA> name <NA> <NA>
        line = f"SPEAKER {file_id} 1 {seg['start']:.3f} {duration:.3f} <NA> <NA> {seg['speaker']} <NA> <NA>"
        output_file.write(line + "\n")
        count += 1
        
    return count

def generate_gold_rttm(merge_threshold, min_duration, prioritize_pog, output_filename):
    dataset_name = "ROG-Dialog"
    base_dir = Path(f"data/{dataset_name}")
    trs_dir = base_dir / "annotations" / "trs"
    output_dir = base_dir / "ref_rttm"

    if not trs_dir.exists():
        print(f"Directory not found: {trs_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    all_trs = list(trs_dir.glob("*.trs"))

    # Grupiranje datotek po ID-ju
    file_groups = {}
    for f in all_trs:
        base_id = f.stem.replace("-std", "").replace("-pog", "")
        file_groups.setdefault(base_id, []).append(f)

    final_name = output_filename if output_filename.endswith(".rttm") else f"{output_filename}.rttm"
    output_path = output_dir / final_name

    total_segments = 0
    with open(output_path, "w", encoding="utf-8") as out_f:
        out_f.write(f"; Generated with merge_threshold={merge_threshold}s, min_duration={min_duration}s, prior_pog={prioritize_pog}, output_filename={final_name}\n")

        for base_id, files in sorted(file_groups.items()):
            std_files = [f for f in files if "-std" in f.name]
            pog_files = [f for f in files if "-pog" in f.name]

            if prioritize_pog:
                selected_file = pog_files[0] if pog_files else (std_files[0] if std_files else files[0])
            else:
                selected_file = std_files[0] if std_files else (pog_files[0] if pog_files else files[0])

            print(f"Processing {base_id} using {selected_file.name}...")
            total_segments += parse_trs_to_rttm(selected_file, out_f, merge_threshold, min_duration)

    print(f"Successfully created Gold RTTM at: {output_path}")
    print(f"Logic: Linear Merge (Threshold: {merge_threshold}s), Source Priority: {'POG' if prioritize_pog else 'STD'}")
    print(f"Total segments written: {total_segments}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate ROG-Dialog gold RTTM",
        epilog="Example: python3 rog_dialog_data_process.py --merge_threshold 1.0 --min_duration 0.1 --prioritize_pog false --output_filename myconfig"
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
        "--output_filename",
        type=str,
        required=True,
        help="(string) Output RTTM filename (with or without .rttm extension). Required."
    )
    args = parser.parse_args()

    generate_gold_rttm(args.merge_threshold, args.min_duration, args.prioritize_pog, args.output_filename)


if __name__ == "__main__":
    main()