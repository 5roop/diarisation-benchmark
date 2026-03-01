# **Reference RTTM Generation for Diarization Benchmark**

This document describes the methodology, design decisions, and parameters used to generate the "Gold Standard" RTTM files for the Diarization Benchmark (specifically for the ROG-Dialog dataset).

## **1\. Source Data**

The reference annotations are derived from **Transcriber (.trs)** files provided by the CLARIN.SI repository.

* **Input Format:** XML-based .trs files.  
* **Content:** The dataset provides two versions for some recordings:  
  * \_std (Standardized): grammatically corrected transcription.  
  * \_pog (Conversational): phonetic transcription including hesitation, false starts, etc.  
* **Selection Logic:** By default, the converter prioritizes \_std files for cleaner sentence boundaries, falling back to \_pog if \_std is unavailable.

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

1. Ensure the data/ROG-Dialog/annotations/trs directory is populated.  
2. Run the conversion script:

```

python convert_trs_to_rttm.py

```

3.  The output will be saved to data/ROG-Dialog/ref\_rttm/gold\_standard.rttm.
