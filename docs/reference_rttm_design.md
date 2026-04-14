# **Reference RTTM Generation for Diarization Benchmark**

This document describes the methodology, design decisions, and parameters used to generate the "Gold Standard" RTTM files for the Diarization Benchmark (specifically for the ROG-Dialog dataset).

## **1\. Source Data**

The reference annotations are derived primarily from **Transcriber (.trs)** files provided by CLARIN.SI (ROG-Dialog/ROG-Art). CCPCL uses **CHAT (.cha)** transcripts from the TalkBank CCPCL corpus.

* **ROG-Dialog / ROG-Art:** XML-based .trs files.  
  * Metadata: `*.trs` with `*Speaker` and `*Turn` segments.
  * Selection: default .std preferred over .pog (if both exist).
* **CCPCL:** CHAT .cha files with time-coded line annotations in the form `*SPEAKER: text start_end` (ms).
  * Conversion: extract speaker/accounted segments and convert to RTTM with linear merge/min-duration heuristics.

## **2\. The "Smoothing" Problem**

Raw manual transcriptions often contain tiny gaps (e.g., 50ms silence for a breath) or strict turn-taking segmentation that splits a single sentence into multiple entries if an interlocutor makes a short sound (e.g., "mhm").

Directly converting these raw segments to RTTM creates an artificially high segment count, which can negatively penalize diarization models that tend to output smoother, continuous segments.

To address this, we apply a **Linear Merging** strategy.

### **Design Decision: Linear Merging vs. Per-Speaker Merging**

We evaluated two strategies for merging adjacent segments of the same speaker:

1. **Per-Speaker Merging (Rejected):**  
   * *Logic:* Merge segments of Speaker A if the gap is small, regardless of whether Speaker B spoke in between.  
   * *Result:* Creates overlaps where none existed in the manual annotation (e.g., Speaker A "talks over" Speaker B's backchannel).  
   * *Verdict:* Rejected because it artificially creates overlapping speech ground truth from non-overlapping data.  
2. **Linear Merging (Selected):**  
   * *Logic:* Merge adjacent segments of Speaker A **only if** no other speaker intervenes.  
   * *Result:* Preserves the strict turn-taking structure of the original dialogue while smoothing out micro-pauses within a single turn.  
   * *Verdict:* Selected as the most faithful representation of the original manual annotation intent suitable for benchmarking ASR/Diarization systems.

## **3\. Tunable Parameters**

The conversion script convert\_trs\_to\_rttm.py uses the following parameters:

### **MERGE\_THRESHOLD \= 1.0s**

* **Definition:** The maximum duration of silence between two segments of the same speaker that will be merged into a single segment.  
* **Reasoning:** Analysis showed that raw annotations often break segments at pauses around 0.5s \- 0.8s. A threshold of 1.0s effectively groups sentences into coherent turns without falsely merging distinct conversational turns separated by significant silence.

### **MIN\_DURATION \= 0.1s**

* **Definition:** Segments shorter than this duration are discarded.  
* **Reasoning:** Manual annotations often contain click sounds, short breaths, or noise marked as speech segments. These micro-segments (\<100ms) are generally below the resolution of standard diarization models and create noise in the DER (Diarization Error Rate) metric (specifically False Alarm errors).

## **4\. Output Format (RTTM)**

The output follows the standard NIST RTTM format:

```

SPEAKER <file_id> 1 <onset> <duration> <NA> <NA> <speaker_id> <NA> <NA>

```

*   
  **File ID:** Normalized filename (removed \_std/\_pog suffixes).  
* **Channel:** Hardcoded to 1 (Mono).  
* **Speaker ID:** Original speaker IDs from the TRS header (e.g., ROG-dialog-0007).

## **5\. Reproducibility**

To regenerate the gold standard RTTM file:

1. Ensure the data/ROG-Dialog/annotations/trs or data/ROG-Art/annotations/trs directory is populated.  
2. Run the dataset-specific conversion script:

```
python rog_dialog_data_process.py --output_filename gold_standard
```

or

```
python rog_art_data_process.py --output_filename gold_standard
```

3. The output will be saved as:
   - data/ROG-Dialog/ref_rttm/gold_standard.rttm or
   - data/ROG-Art/ref_rttm/gold_standard.rttm or
   - data/CHILDES-CCPCL/ref_rttm/ccpcl_gold_standard.rttm

For CCPCL, use:
```
python ccpcl_data_process.py --cha_dir data/raw/CCPCL/CCPCL --output_file data/CHILDES-CCPCL/ref_rttm/ccpcl_gold_standard.rttm
```


