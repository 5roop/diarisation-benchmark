import argparse
import os
from collections import defaultdict
from pathlib import Path

def parse_rttm(file_path):
    """
    Parses RTTM file into a structured dictionary.
    Structure: data[file_id] = {
        'total_duration': float,
        'segment_count': int,
        'speakers': set(),
        'segments': list of dicts
    }
    """
    stats = defaultdict(lambda: {
        'total_duration': 0.0, 
        'segment_count': 0, 
        'speakers': set(),
        'segments': []
    })
    
    global_speakers = set()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 8: continue
            
            # Format: SPEAKER file_id 1 start duration <NA> <NA> spk_id <NA> <NA>
            file_id = parts[1]
            start = float(parts[3])
            duration = float(parts[4])
            spk_id = parts[7]
            
            stats[file_id]['total_duration'] += duration
            stats[file_id]['segment_count'] += 1
            stats[file_id]['speakers'].add(spk_id)
            stats[file_id]['segments'].append({
                'start': start, 
                'end': start + duration, 
                'speaker': spk_id
            })
            global_speakers.add(spk_id)
            
    return stats, global_speakers

def print_diff(label, val1, val2, is_float=False):
    diff = val1 - val2
    if is_float:
        return f"{val1:>10.2f} | {val2:>10.2f} | {diff:>+10.2f}"
    else:
        return f"{val1:>10} | {val2:>10} | {diff:>+10}"

def analyze_gaps(segments, threshold=0.5):
    """Counts gaps smaller than threshold for the same speaker."""
    # Group by speaker
    spk_segs = defaultdict(list)
    for s in segments:
        spk_segs[s['speaker']].append(s)
    
    short_gaps = 0
    for spk, items in spk_segs.items():
        items.sort(key=lambda x: x['start'])
        for i in range(len(items) - 1):
            gap = items[i+1]['start'] - items[i]['end']
            if 0 < gap < threshold:
                short_gaps += 1
    return short_gaps

def main():
    parser = argparse.ArgumentParser(description="Compare two RTTM files (Reference vs Hypothesis/Other Ref).")
    parser.add_argument("ref", help="Path to reference RTTM (File A)")
    parser.add_argument("hyp", help="Path to hypothesis/comparison RTTM (File B)")
    args = parser.parse_args()

    if not os.path.exists(args.ref) or not os.path.exists(args.hyp):
        print("Error: One or both files do not exist.")
        return

    print(f"--- RTTM COMPARISON TOOL ---")
    print(f"File A (Ref): {args.ref}")
    print(f"File B (Hyp): {args.hyp}")
    print("="*60)

    # 1. Load Data
    data_a, spk_a = parse_rttm(args.ref)
    data_b, spk_b = parse_rttm(args.hyp)

    # 2. Global Stats
    total_dur_a = sum(d['total_duration'] for d in data_a.values())
    total_dur_b = sum(d['total_duration'] for d in data_b.values())
    total_seg_a = sum(d['segment_count'] for d in data_a.values())
    total_seg_b = sum(d['segment_count'] for d in data_b.values())
    
    print(f"{'METRIC':<20} | {'FILE A':>10} | {'FILE B':>10} | {'DIFF':>10}")
    print("-" * 60)
    print(f"{'Total Files':<20} | {print_diff('', len(data_a), len(data_b))}")
    print(f"{'Total Speakers':<20} | {print_diff('', len(spk_a), len(spk_b))}")
    print(f"{'Total Segments':<20} | {print_diff('', total_seg_a, total_seg_b)}")
    print(f"{'Total Duration (s)':<20} | {print_diff('', total_dur_a, total_dur_b, True)}")
    print("="*60)

    # 3. File-by-File Analysis
    all_files = set(data_a.keys()) | set(data_b.keys())
    print("\n--- PER-FILE BREAKDOWN ---")
    print(f"{'FILE ID':<25} | {'DUR A (s)':>10} | {'DUR B (s)':>10} | {'DIFF (s)':>10} | {'SPK A':>5} | {'SPK B':>5}")
    print("-" * 80)
    
    for fid in sorted(all_files):
        if fid not in data_a:
            print(f"{fid:<25} | {'MISSING':>10} | {data_b[fid]['total_duration']:>10.1f} | {'N/A':>10} | {'-':>5} | {len(data_b[fid]['speakers']):>5}")
            continue
        if fid not in data_b:
            print(f"{fid:<25} | {data_a[fid]['total_duration']:>10.1f} | {'MISSING':>10} | {'N/A':>10} | {len(data_a[fid]['speakers']):>5} | {'-':>5}")
            continue
            
        dur_a = data_a[fid]['total_duration']
        dur_b = data_b[fid]['total_duration']
        spk_cnt_a = len(data_a[fid]['speakers'])
        spk_cnt_b = len(data_b[fid]['speakers'])
        
        print(f"{fid:<25} | {dur_a:>10.1f} | {dur_b:>10.1f} | {dur_a-dur_b:>+10.1f} | {spk_cnt_a:>5} | {spk_cnt_b:>5}")

    # 4. Smoothing/Gap Analysis
    print("\n--- SMOOTHING ANALYSIS (Gaps < 0.5s within same speaker) ---")
    gaps_a = sum(analyze_gaps(d['segments']) for d in data_a.values())
    gaps_b = sum(analyze_gaps(d['segments']) for d in data_b.values())
    print(f"File A Short Gaps: {gaps_a}")
    print(f"File B Short Gaps: {gaps_b}")
    
    if gaps_a > 500 and gaps_b < 100:
        print("-> CONCLUSION: File B likely uses aggressive smoothing/merging.")
    elif gaps_b > 500 and gaps_a < 100:
         print("-> CONCLUSION: File A likely uses aggressive smoothing/merging.")
    elif abs(gaps_a - gaps_b) < 100:
        print("-> CONCLUSION: Similar smoothing strategies used.")

if __name__ == "__main__":
    main()