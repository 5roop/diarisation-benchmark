#!/bin/bash

# Prekini izvajanje ob napaki
set -e

# Ime dataseta - enostavno spremenljivo za prihodnje datasete
DATASET_NAME="ROG-Dialog"
BASE_DIR="data/$DATASET_NAME"

echo "=== 1. Preverjam, ali je dataset že organiziran: $DATASET_NAME ==="
mkdir -p "$BASE_DIR/audio"
mkdir -p "$BASE_DIR/annotations/trs"
mkdir -p "$BASE_DIR/annotations/exb"
mkdir -p "$BASE_DIR/annotations/exs"
mkdir -p "$BASE_DIR/docs"
mkdir -p "$BASE_DIR/ref_rttm"  # Preimenovano v rttm
mkdir -p data/raw

SKIP_REORG=false
if [ -d "$BASE_DIR/audio" ] && [ -d "$BASE_DIR/annotations/trs" ] && [ -d "$BASE_DIR/annotations/exb" ] && [ -d "$BASE_DIR/annotations/exs" ] && [ -d "$BASE_DIR/docs" ]; then
    if [ "$(ls -A "$BASE_DIR/audio" 2>/dev/null)" ] && [ "$(ls -A "$BASE_DIR/annotations/trs" 2>/dev/null)" ] && [ "$(ls -A "$BASE_DIR/annotations/exb" 2>/dev/null)" ] && [ "$(ls -A "$BASE_DIR/annotations/exs" 2>/dev/null)" ]; then
        echo "Dataset že organiziran; preskočim prenose/razširjanje/reorganizacijo."
        SKIP_REORG=true
    fi
fi

if [ "$SKIP_REORG" = true ]; then
    echo "=== Preskakujem prenos in reorganizacijo ==="
else
    # Premik v mapo za prenose
    cd data/raw

    echo "=== 2. Prenašam datoteke ==="
if [ ! -f "ROG-Dialog.zip" ] || [ ! -f "ROG-Dialog_audio.zip" ]; then
    echo "Prenašam s CLARIN.SI..."
    curl --remote-name-all https://www.clarin.si/repository/xmlui/bitstream/handle/11356/2073{/ROG-Dialog.zip,/ROG-Dialog_audio.zip}
else
    echo "Datoteke že obstajajo."
fi

echo "=== 3. Razširjam arhive ==="
unzip -q -o ROG-Dialog_audio.zip
unzip -q -o ROG-Dialog.zip

echo "=== 4. Reorganiziram v '$BASE_DIR' ==="
cd ../..
fi

# Audio
if [ -d "data/raw/ROG-Dialog/DATA/WAV" ]; then
    mv data/raw/ROG-Dialog/DATA/WAV/*.wav "$BASE_DIR/audio/"
fi

# Annotations (TRS, EXB, EXS)
if [ -d "data/raw/ROG-Dialog/DATA/TRS" ]; then
    mv data/raw/ROG-Dialog/DATA/TRS/*.trs "$BASE_DIR/annotations/trs/"
fi
if [ -d "data/raw/ROG-Dialog/DATA/EXB" ]; then
    mv data/raw/ROG-Dialog/DATA/EXB/*.exb "$BASE_DIR/annotations/exb/"
fi
if [ -d "data/raw/ROG-Dialog/DATA/EXS" ]; then
    mv data/raw/ROG-Dialog/DATA/EXS/*.exs "$BASE_DIR/annotations/exs/"
fi

# Docs
if [ -d "data/raw/ROG-Dialog/DOCS" ]; then
    mv data/raw/ROG-Dialog/DOCS/* "$BASE_DIR/docs/"
fi

echo "=== 5. Čiščenje ==="
rm -rf data/raw/ROG-Dialog

OUTPUT_FILENAME="${1:-default_gold_standard}"
if [[ "$OUTPUT_FILENAME" != *.rttm ]]; then
    OUTPUT_FILENAME="$OUTPUT_FILENAME.rttm"
fi

echo "=== 6. Generiram gold_standard RTTM ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/rog_dialog_data_process.py" --merge_threshold 1.0 --min_duration 0.1 --prioritize_pog false --output_filename "$OUTPUT_FILENAME"

echo "=== KONČANO! ==="
echo "Dataset $DATASET_NAME je pripravljen."