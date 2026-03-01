"""
Diarisation Benchmark - Report Generator
=========================================
Project: diarisation-benchmark
Description: Generates comprehensive benchmark reports with visualizations for
             speaker diarization model evaluations. Calculates DER, Purity, and
             Coverage metrics across all models in the results directory. Supports
             dataset-specific errata rules via UEM (Universal Evaluation Maps) to
             handle transcription errors in the ROG-Dialog gold standard.

Author: Tomaž Savodnik
Date: March 2026
"""
import argparse
import os
import glob
import json
import re
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path
from pyannote.core import Segment, Annotation, Timeline
from pyannote.metrics.diarization import DiarizationErrorRate, DiarizationPurity, DiarizationCoverage
from tabulate import tabulate
import warnings

# Utišamo opozorila
warnings.filterwarnings("ignore")

# --- KONFIGURACIJA ---
COLLAR_SETTINGS = [0.0, 0.25]
SKIP_OVERLAP = False 

def fix_permissions(path, uid, gid):
    print(f"Fixing permissions for {path} -> {uid}:{gid}...", flush=True)
    try:
        if os.path.isfile(path):
            os.chown(path, uid, gid)
            return
        os.chown(path, uid, gid)
        for root, dirs, files in os.walk(path):
            for d in dirs: os.chown(os.path.join(root, d), uid, gid)
            for f in files: os.chown(os.path.join(root, f), uid, gid)
    except Exception: pass

def normalize_speaker_label(label):
    """Združi SPEAKER_00 in speaker_0 v 'Speaker 0'."""
    m = re.match(r'(?i)^speaker[_\s]*(\d+)$', label)
    if m:
        return f"Speaker {int(m.group(1))}"
    return label

def load_rttm(file_path):
    annotations = {}
    if not os.path.exists(file_path): return {}
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 8: continue
            
            file_id = parts[1]
            start = float(parts[3])
            duration = float(parts[4])
            label = normalize_speaker_label(parts[7])
            
            if file_id not in annotations:
                annotations[file_id] = Annotation(uri=file_id)
            annotations[file_id][Segment(start, start + duration)] = label
    return annotations

def load_metadata(speeches_path):
    try:
        df = pd.read_csv(speeches_path, sep='\t')
        df.columns = df.columns.str.strip()
        meta = {}
        for _, row in df.iterrows():
            rec_id = str(row['RECORDING-ID'])
            meta[rec_id] = {
                'Domain': row.get('DOMAIN', 'Unknown'),
                'Type': row.get('TYPE', 'Unknown'),
                'Quality': row.get('RECORDING QUALITY', 'Unknown'),
                'Device': row.get('RECORDING DEVICE', 'Unknown'),
                'Title': row.get('TITLE', ''),
                'Keywords': row.get('KEYWORDS', '')
            }
        return meta
    except Exception as e:
        print(f"WARNING: Could not load metadata TSV: {e}", flush=True)
        return {}

def get_hardware_stats(model_dir):
    json_path = os.path.join(model_dir, "benchmark_metadata.json")
    if not os.path.exists(json_path): return None, {}
    try:
        with open(json_path, 'r') as f: data = json.load(f)
        
        global_stats = {
            'model_name': data.get('model_name', os.path.basename(model_dir)),
            'gpu_name': data.get('run_info', {}).get('gpu_name', 'Unknown'),
            'overall_rtf': data.get('timings', {}).get('overall_rtf', 0.0),
            'max_vram': data.get('timings', {}).get('max_vram_peak_mb', 0.0),
            'files_processed': len(data.get('files', []))
        }
        file_stats = {}
        for f_data in data.get('files', []):
            fname = f_data.get('filename')
            if fname:
                file_stats[fname] = {
                    'rtf': f_data.get('rtf', 0.0),
                    'vram': f_data.get('peak_vram_mb', 0.0),
                    'duration': f_data.get('audio_duration_s', 0.0),
                    'error': f_data.get('error', None)
                }
        return global_stats, file_stats
    except: return None, {}

def evaluate_model_comprehensive(model_dir, gold_annotations, collar, hw_file_stats, errata_dict):
    rttm_files = glob.glob(os.path.join(model_dir, "*.rttm"))
    system_annotations = {}
    for f in rttm_files:
        fname = Path(f).stem
        system_annotations[fname] = load_rttm(f).get(fname, Annotation(uri=fname))

    metric_der = DiarizationErrorRate(collar=collar, skip_overlap=SKIP_OVERLAP)
    metric_purity = DiarizationPurity(collar=collar, skip_overlap=SKIP_OVERLAP)
    metric_coverage = DiarizationCoverage(collar=collar, skip_overlap=SKIP_OVERLAP)
    
    file_results = []
    acc = {'total':0, 'error':0, 'p_num':0, 'p_den':0, 'c_num':0, 'c_den':0}
    
    for fid, ref in gold_annotations.items():
        hw = hw_file_stats.get(fid, {})
        res_entry = {
            'File ID': fid, 'Status': 'OK', 
            'RTF': hw.get('rtf', None), 'VRAM': hw.get('vram', None)
        }

        ref_tl = ref.get_timeline()
        ref_end = ref_tl.extent().end if not ref_tl.empty() else 0.0
        audio_dur = hw.get('duration') or ref_end
        
        eval_end = audio_dur
        if fid in errata_dict and 'trim_end' in errata_dict[fid]:
            eval_end = errata_dict[fid]['trim_end']
            
        uem = Timeline([Segment(0.0, eval_end)])

        has_output = fid in system_annotations and len(system_annotations[fid]) > 0
        if hw.get('error'): has_output = False

        if has_output:
            hyp = system_annotations[fid]
            stats = metric_der(ref, hyp, detailed=True, uem=uem)
            purity = metric_purity(ref, hyp, uem=uem)
            coverage = metric_coverage(ref, hyp, uem=uem)
            
            total = stats.get('total', 0.0)
            miss = stats.get('missed detection', 0.0)
            fa = stats.get('false alarm', 0.0)
            conf = stats.get('confusion', 0.0)
            
            acc['total'] += total
            acc['error'] += (miss + fa + conf)
            
            hyp_eval = hyp.crop(uem)
            ref_eval = ref.crop(uem)
            
            hyp_dur = hyp_eval.get_timeline().duration()
            ref_dur = ref_eval.get_timeline().duration()
            
            acc['p_num'] += purity * hyp_dur; acc['p_den'] += hyp_dur
            acc['c_num'] += coverage * ref_dur; acc['c_den'] += ref_dur

            res_entry.update({
                'DER': (stats.get('diarization error rate', 0.0)) * 100 if total > 0 else 0.0,
                'Miss': (miss / total * 100) if total > 0 else 0.0,
                'FA': (fa / total * 100) if total > 0 else 0.0,
                'Conf': (conf / total * 100) if total > 0 else 0.0,
                'Purity': purity * 100,
                'Cover': coverage * 100,
                'Total Speech': total
            })
        else:
            ref_eval = ref.crop(uem)
            ref_speech_duration = sum(s.duration for s, _ in ref_eval.itertracks(yield_label=False))
            
            acc['total'] += ref_speech_duration
            acc['error'] += ref_speech_duration 
            acc['c_den'] += ref_speech_duration
            
            res_entry.update({
                'Status': 'FAIL', 'DER': 100.0, 'Miss': 100.0, 'FA': 0.0, 'Conf': 0.0,
                'Purity': 0.0, 'Cover': 0.0, 'Total Speech': ref_speech_duration
            })
            if hw.get('error'): res_entry['Status'] = "OOM/ERR"

        file_results.append(res_entry)

    g_der = (acc['error'] / acc['total'] * 100) if acc['total'] > 0 else 0.0
    g_pur = (acc['p_num'] / acc['p_den'] * 100) if acc['p_den'] > 0 else 0.0
    g_cov = (acc['c_num'] / acc['c_den'] * 100) if acc['c_den'] > 0 else 0.0
    
    return {'der': g_der, 'purity': g_pur, 'coverage': g_cov, 'files': file_results}

def find_extreme_segments(ref, systems_dict, window_duration=60.0, step=30.0, min_speech=15.0, eval_boundary=None):
    """
    Skenira posnetek z drsečim oknom in poišče 60s izsek z najboljšim in najslabšim povprečnim DER.
    """
    max_time = ref.get_timeline().extent().end if not ref.get_timeline().empty() else 0.0
    if eval_boundary and eval_boundary < max_time:
        max_time = eval_boundary
        
    max_start = max_time - window_duration
    if max_start <= 0:
        return None, None
        
    best_seg = None
    worst_seg = None
    min_der = float('inf')
    max_der = -1.0
    
    # Validiramo sisteme
    val_sys = [hyp for hyp in systems_dict.values() if hyp and not hyp.get_timeline().empty()]
    if not val_sys: return None, None
    
    for start in np.arange(0, max_start + 1, step):
        seg = Segment(start, start + window_duration)
        uem = Timeline([seg])
        
        # Preverimo, če je v tem oknu sploh dovolj govora
        ref_crop = ref.crop(uem)
        speech_dur = sum(s.duration for s, _ in ref_crop.itertracks(yield_label=False))
        
        if speech_dur < min_speech:
            continue
            
        total_der = 0.0
        for hyp in val_sys:
            # Izračun on-the-fly (hitra instanciacija)
            metric = DiarizationErrorRate(skip_overlap=SKIP_OVERLAP)
            stats = metric(ref, hyp, detailed=True, uem=uem)
            if stats.get('total', 0) > 0:
                der = stats['diarization error rate'] * 100
            else:
                der = 0.0
            total_der += der
        
        avg_der = total_der / len(val_sys)
        
        if avg_der < min_der:
            min_der = avg_der
            best_seg = seg
        if avg_der > max_der:
            max_der = avg_der
            worst_seg = seg
            
    return best_seg, worst_seg

def plot_timeline(gold_annot, system_annots_dict, file_id, output_dir, eval_boundary=None, crop_segment=None, title_prefix="Timeline Analysis", suffix=""):
    """
    Risanje gantograma. Zna izrisati celoto ali 'zoomiran' izsek (crop_segment).
    Barve ostanejo dosledne ne glede na crop, ker se izračunajo na celotni datoteki.
    """
    valid_systems = {k: v for k, v in system_annots_dict.items() if v}
    if not valid_systems: return
    
    # 1. OPTIMAL MAPPING NA CELOTNI DATOTEKI (Za dosledne barve)
    metric = DiarizationErrorRate(skip_overlap=SKIP_OVERLAP)
    uem_full = Timeline([Segment(0.0, eval_boundary)]) if eval_boundary else None
    
    mapped_systems = {}
    all_speakers = set(gold_annot.labels())
    
    for model_name, hyp in valid_systems.items():
        mapping = metric.optimal_mapping(gold_annot, hyp, uem=uem_full)
        mapped_hyp = Annotation(uri=hyp.uri)
        for seg, trk, lbl in hyp.itertracks(yield_label=True):
            new_lbl = mapping.get(lbl, f"{lbl} (unmapped)")
            mapped_hyp[seg, trk] = new_lbl
            all_speakers.add(new_lbl)
        mapped_systems[model_name] = mapped_hyp

    all_speakers = sorted(list(all_speakers))
    
    # 2. DEFINICIJA BARV
    if len(all_speakers) <= 9:
        palette = sns.color_palette("Set1", n_colors=len(all_speakers))
    else:
        palette = sns.color_palette("tab20", n_colors=max(20, len(all_speakers)))
    spk_color_map = dict(zip(all_speakers, palette))
    
    # 3. CROPPING (Če želimo prikazati le izsek)
    if crop_segment:
        gold_to_plot = gold_annot.crop(crop_segment)
        sys_to_plot = {k: v.crop(crop_segment) for k, v in mapped_systems.items()}
        min_x = crop_segment.start
        max_x = crop_segment.end
    else:
        gold_to_plot = gold_annot
        sys_to_plot = mapped_systems
        min_x = 0
        max_x = gold_annot.get_timeline().extent().end if not gold_annot.get_timeline().empty() else 0
        for hyp in mapped_systems.values():
            if not hyp.get_timeline().empty():
                max_x = max(max_x, hyp.get_timeline().extent().end)
                
    # 4. IZRIS
    plt.figure(figsize=(14, max(4, len(valid_systems)*0.8 + 2)))
    y_pos = 0
    y_ticks, y_tick_labels = [], []
    
    # Gold Standard
    for seg, _, lbl in gold_to_plot.itertracks(yield_label=True):
        plt.broken_barh([(seg.start, seg.duration)], (y_pos, 0.6), facecolors=spk_color_map.get(lbl, 'gray'))
    y_ticks.append(y_pos + 0.3); y_tick_labels.append("GOLD")
    y_pos -= 1.0
    
    # Modeli
    for model_name in sorted(sys_to_plot.keys()):
        hyp = sys_to_plot[model_name]
        for seg, _, lbl in hyp.itertracks(yield_label=True):
            color = spk_color_map.get(lbl, 'gray')
            plt.broken_barh([(seg.start, seg.duration)], (y_pos, 0.6), facecolors=color)
        y_ticks.append(y_pos + 0.3); y_tick_labels.append(model_name)
        y_pos -= 1.0
        
    # Narišemo mejo evalvacije, če je vidna v trenutnem oknu
    if eval_boundary and min_x <= eval_boundary <= max_x and not crop_segment:
        plt.axvline(x=eval_boundary, color='red', linestyle='--', linewidth=2, label='Eval Boundary')
        plt.axvspan(eval_boundary, max_x + 10, color='gray', alpha=0.2)
        plt.text(eval_boundary + 5, 0.5, "IGNORED IN EVAL", color='red', weight='bold', rotation=90)
        
    # Dinamične meje X osi
    if crop_segment:
        plt.xlim(min_x, max_x)
    else:
        plt.xlim(0, max(max_x, eval_boundary if eval_boundary else 0) + 10)
        
    plt.xlabel("Time (s)")
    plt.yticks(y_ticks, y_tick_labels)
    
    time_str = f" [{min_x:.1f}s - {max_x:.1f}s]" if crop_segment else ""
    plt.title(f"{title_prefix}: {file_id}{time_str}")
    plt.grid(True, axis='x', linestyle='--', alpha=0.5)
    
    # Zmanjšamo legendo samo na tiste, ki so DEJANSKO vidni v tem oknu
    visible_speakers = set(gold_to_plot.labels())
    for hyp in sys_to_plot.values():
        visible_speakers.update(hyp.labels())
        
    patches = [mpatches.Patch(color=spk_color_map[s], label=s) for s in sorted(list(visible_speakers))[:20]]
    if eval_boundary and min_x <= eval_boundary <= max_x and not crop_segment:
        patches.append(mpatches.Patch(color='gray', alpha=0.2, label='Ignored Region'))
        
    plt.legend(handles=patches, bbox_to_anchor=(1.01, 1), loc='upper left')
    plt.tight_layout(rect=[0, 0, 0.9, 1])
    plt.savefig(os.path.join(output_dir, f"timeline_{file_id}{suffix}.png"), dpi=150, bbox_inches='tight')
    plt.close()

def fmt_rtf(r):
    try:
        val = float(r)
        if 0 < val < 0.01: return "< 0.01"
        return f"{val:.2f}"
    except: return r

def fmt_vram(v):
    try:
        val = float(v)
        if val == 0: return "0.0"
        return f"{val/1024:.1f}"
    except: return v

def highlight_best(df, min_cols=[], max_cols=[], formatters={}):
    """Formats table with bold best values based on formatters."""
    df_out = df.copy()
    for col in df.columns:
        if col not in min_cols and col not in max_cols:
            if col in formatters:
                df_out[col] = df[col].apply(lambda x: formatters[col](x) if pd.notna(x) else x)
            continue
            
        vals = pd.to_numeric(df[col], errors='coerce')
        best = vals.min() if col in min_cols else vals.max()
        formatter = formatters.get(col, lambda x: f"{float(x):.2f}")
        
        def apply_fmt(x):
            try:
                val = float(x)
                fmt_val = formatter(val)
                return f"**{fmt_val}**" if val == best else fmt_val
            except: return x
        df_out[col] = df[col].apply(apply_fmt)
    return df_out

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", required=True)
    parser.add_argument("--results_dir", required=True)
    parser.add_argument("--metadata", help="Path to TSV")
    parser.add_argument("--errata", default="DATASET_ERRATA.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    gold_annots = load_rttm(args.gold)
    meta_dict = load_metadata(args.metadata) if args.metadata else {}
    
    errata_dict = {}
    if os.path.exists(args.errata):
        try:
            with open(args.errata, 'r') as f: errata_dict = json.load(f)
        except: pass

    model_dirs = [f.path for f in os.scandir(args.results_dir) if f.is_dir()]

    summary_data = []
    deep_dive_data = {fid: {} for fid in gold_annots.keys()}
    model_links = {}

    print(f"Processing {len(model_dirs)} models...", flush=True)

    for model_dir in model_dirs:
        hw_global, hw_per_file = get_hardware_stats(model_dir)
        if not hw_global: continue
        
        short_name = os.path.basename(model_dir)
        display_name = short_name.replace('_', ' ').replace('-', ' ')
        model_links[display_name] = hw_global['model_name']

        for collar in COLLAR_SETTINGS:
            res = evaluate_model_comprehensive(model_dir, gold_annots, collar, hw_per_file, errata_dict)
            
            ok_count = sum(1 for f in res['files'] if f['Status'] == 'OK')
            summary_data.append({
                "Model": display_name, "Collar": collar,
                "DER": res['der'], "Purity": res['purity'], "Cover": res['coverage'],
                "Miss": sum(f.get('Miss', 0) for f in res['files'] if f['Status']=='OK') / ok_count if ok_count else 0,
                "FA": sum(f.get('FA', 0) for f in res['files'] if f['Status']=='OK') / ok_count if ok_count else 0,
                "Conf": sum(f.get('Conf', 0) for f in res['files'] if f['Status']=='OK') / ok_count if ok_count else 0,
                "RTF": hw_global['overall_rtf'], "VRAM": hw_global['max_vram'],
                "Completed": f"{ok_count}/{len(gold_annots)}"
            })

            if collar == 0.25:
                for fstat in res['files']:
                    deep_dive_data[fstat['File ID']][display_name] = fstat

    df_sum = pd.DataFrame(summary_data)

    print("Generating plots...", flush=True)
    sns.set_theme(style="whitegrid")
    
    plt.figure(figsize=(12, 6))
    sns.barplot(data=df_sum, x="Model", y="DER", hue="Collar", palette="viridis")
    plt.title("Impact of Collar on DER")
    plt.ylabel("DER (%)")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(os.path.join(args.output, "plot_der_comparison.png"))
    plt.close()

    all_file_rows = []
    for fid, models_data in deep_dive_data.items():
        domain = meta_dict.get(fid, {}).get('Domain', 'N/A')
        for m_name, stats in models_data.items():
            if stats['Status'] == 'OK':
                all_file_rows.append({'Domain': domain, 'DER': stats['DER'], 'Model': m_name})
    
    df_dom = pd.DataFrame()
    domain_table_md = ""
    if all_file_rows:
        df_dom = pd.DataFrame(all_file_rows)
        plt.figure(figsize=(14, 6))
        sns.boxplot(data=df_dom, x="Domain", y="DER", hue="Model")
        plt.title("DER Distribution by Domain")
        plt.xticks(rotation=45, ha='right')
        plt.legend(bbox_to_anchor=(1.01, 1), loc='upper left', borderaxespad=0.)
        plt.tight_layout()
        plt.savefig(os.path.join(args.output, "plot_domain_analysis.png"), bbox_inches='tight')
        plt.close()

        pivot_dom = df_dom.pivot_table(index="Domain", columns="Model", values="DER", aggfunc="mean")
        pivot_dom["AVG"] = pivot_dom.mean(axis=1)
        
        m_names = [c for c in pivot_dom.columns if c != "AVG"]
        col_map = {m: chr(65+i) for i, m in enumerate(m_names)}
        
        legend_txt = "\n".join([f"* **{col_map[m]}**: {m}" for m in m_names])
        
        pivot_dom = pivot_dom.rename(columns=col_map).reset_index()
        
        for idx, row in pivot_dom.iterrows():
            vals = pd.to_numeric(row[list(col_map.values())], errors='coerce')
            min_v = vals.min()
            for c in col_map.values():
                try:
                    if float(row[c]) == min_v: pivot_dom.at[idx, c] = f"**{float(row[c]):.2f}**"
                    else: pivot_dom.at[idx, c] = f"{float(row[c]):.2f}"
                except: pass
            pivot_dom.at[idx, "AVG"] = f"{float(row['AVG']):.2f}"
        
        domain_table_md = tabulate(pivot_dom, headers="keys", tablefmt="github", showindex=False) + "\n\n" + legend_txt

    print("Writing report...", flush=True)
    formatters = {
        "RTF": fmt_rtf,
        "VRAM": fmt_vram,
        "DER": lambda x: f"{x:.2f}",
        "Miss": lambda x: f"{x:.2f}",
        "FA": lambda x: f"{x:.2f}",
        "Conf": lambda x: f"{x:.2f}",
        "Purity": lambda x: f"{x:.2f}",
        "Cover": lambda x: f"{x:.2f}"
    }

    with open(os.path.join(args.output, "ROG_Dia_Benchmark_Report.md"), "w") as f:
        f.write(f"# ROG-Dia Benchmark Report\n\n**Date:** {pd.Timestamp.now().date()}\n\n")
        
        f.write("## 1. Evaluated Models\n")
        for disp_name, full_name in sorted(model_links.items()):
            f.write(f"* **{disp_name}** (`{full_name}`) - [HuggingFace](https://huggingface.co/{full_name})\n")
        f.write("\n")

        f.write("## 2. Executive Summary\n\n")
        df_lead = df_sum[df_sum["Collar"] == 0.25].copy()
        df_lead = df_lead.rename(columns={"VRAM": "VRAM (GB)"})
        formatters["VRAM (GB)"] = fmt_vram
        
        df_lead = df_lead.sort_values("DER")
        df_lead = highlight_best(df_lead, min_cols=["DER", "Miss", "FA", "Conf", "RTF", "VRAM (GB)"], max_cols=["Purity", "Cover"], formatters=formatters)
        
        f.write(tabulate(df_lead, headers="keys", tablefmt="github", showindex=False))
        f.write("\n\n### Terminology & Methodology\n")
        f.write("* **DER (Diarization Error Rate):** Primary metric. Lower is better. Sum of Missed, False Alarm, and Confusion rates.\n")
        f.write("* **Miss (%):** Speech present in Gold Standard but missed by the model.\n")
        f.write("* **FA (False Alarm %):** Model predicted speech where Gold Standard is silent.\n")
        f.write("* **Conf (Confusion %):** Speech correctly detected but assigned to the wrong speaker.\n")
        f.write("* **Purity (%):** Evaluates cluster purity. High purity = when a model identifies a speaker, it is consistently the same person.\n")
        f.write("* **Cover (Coverage %):** Evaluates how much of the original speaker's speech was captured under a single hypothesis cluster.\n")
        f.write("* **RTF (Real Time Factor):** Processing time divided by audio length. e.g., `< 0.01` means exceptionally fast processing.\n")
        f.write("* **VRAM (GB):** Peak GPU memory utilized. `0.0 GB` indicates an API/Cloud-based model.\n\n")

        if errata_dict:
            f.write("## 3. Dataset Errata (Corrections Applied)\n")
            f.write("Corrections automatically applied via Universal Evaluation Maps (UEM) to account for transcription errors. Models are not penalized for predictions outside these boundaries.\n\n")
            for fid, err in errata_dict.items():
                f.write(f"* **`{fid}`**: Evaluated only up to {err.get('trim_end', 'EOF')}s. *Reason: {err.get('reason', 'N/A')}*\n")
            f.write("\n")

        f.write("## 4. Visual & Domain Analysis\n")
        f.write("![DER Comparison](plot_der_comparison.png)\n\n")
        f.write("![Domain Analysis](plot_domain_analysis.png)\n\n")
        
        if domain_table_md:
            f.write("### Domain Comparison (DER %)\n")
            f.write("Average DER per domain. **Bold** highlights the best model for each domain.\n\n")
            f.write(domain_table_md)
            f.write("\n\n")

        f.write("## 5. Deep Dive: File-by-File Analysis\n")
        f.write("Detailed breakdown for every file. *For metric definitions, see Executive Summary.*\n\n")
        
        for fid in sorted(deep_dive_data.keys()):
            meta = meta_dict.get(fid, {})
            f.write(f"### File: {fid}\n\n")
            f.write(f"**Domain:** {meta.get('Domain', '-')} | **Quality:** {meta.get('Quality', '-')} | **Device:** {meta.get('Device', '-')}\n\n")
            if meta.get('Title'): f.write(f"> *{meta.get('Title')}*\n\n")
            
            if fid in errata_dict:
                f.write(f"> ⚠️ **ERRATA APPLIED**: Evaluation bounded to {errata_dict[fid].get('trim_end')}s.\n\n")

            # --- Full Timeline ---
            file_annots = {}
            for m_dir in model_dirs:
                short = os.path.basename(m_dir)
                disp_n = short.replace('_', ' ').replace('-', ' ')
                rttm = os.path.join(m_dir, f"{fid}.rttm")
                if os.path.exists(rttm): file_annots[disp_n] = load_rttm(rttm).get(fid, Annotation())
            
            eval_bound = errata_dict.get(fid, {}).get('trim_end', None) if fid in errata_dict else None
            
            if fid in gold_annots:
                plot_timeline(gold_annots[fid], file_annots, fid, args.output, eval_boundary=eval_bound, suffix="_full")
                f.write(f"![Full Timeline {fid}](timeline_{fid}_full.png)\n\n")
                
                # --- 60-Second Zoom Snippets ---
                best_seg, worst_seg = find_extreme_segments(gold_annots[fid], file_annots, window_duration=60.0, step=30.0, min_speech=15.0, eval_boundary=eval_bound)
                
                if best_seg and worst_seg:
                    f.write("#### 60-Second Snippets (Zoom-in)\n")
                    f.write("Below are 60-second zoomed-in windows showing where the models performed best and worst (based on average DER).\n\n")
                    
                    # Risanje Best Snippet
                    plot_timeline(gold_annots[fid], file_annots, fid, args.output, eval_boundary=eval_bound, crop_segment=best_seg, title_prefix="BEST Segment (Lowest Avg DER)", suffix="_best")
                    f.write(f"![Best Segment {fid}](timeline_{fid}_best.png)\n\n")
                    
                    # Risanje Worst Snippet
                    plot_timeline(gold_annots[fid], file_annots, fid, args.output, eval_boundary=eval_bound, crop_segment=worst_seg, title_prefix="WORST Segment (Highest Avg DER)", suffix="_worst")
                    f.write(f"![Worst Segment {fid}](timeline_{fid}_worst.png)\n\n")

            # --- Tabela Metrik ---
            rows = []
            for m_name, stats in deep_dive_data[fid].items():
                row = {'Model': m_name}
                if stats['Status'] == 'OK':
                    row.update({
                        'DER': stats['DER'], 'Miss': stats['Miss'], 'FA': stats['FA'],
                        'Conf': stats['Conf'], 'Pur': stats['Purity'], 'Cov': stats['Cover'],
                        'VRAM (GB)': stats['VRAM']
                    })
                else:
                    row['Status'] = stats['Status']
                rows.append(row)
            
            if rows:
                df_f = pd.DataFrame(rows).sort_values("DER")
                df_f = highlight_best(df_f, min_cols=["DER", "Miss", "FA", "Conf", "VRAM (GB)"], max_cols=["Pur", "Cov"], formatters=formatters)
                f.write(tabulate(df_f, headers="keys", tablefmt="github", showindex=False))
            f.write("\n\n---\n\n")

    try:
        uid = int(os.environ.get("HOST_UID", 0))
        gid = int(os.environ.get("HOST_GID", 0))
        if uid > 0: fix_permissions(args.output, uid, gid)
    except: pass
    print(f"Done. Report at {args.output}")

if __name__ == "__main__":
    main()