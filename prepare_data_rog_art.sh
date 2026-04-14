#!/bin/bash

# Prekini izvajanje ob napaki
set -e

DATASET_NAME="ROG-Art"
RAW_DIR="data/raw"
DEST_DIR="data/$DATASET_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== 1. Preverjam, ali je dataset že organiziran: $DATASET_NAME ==="
mkdir -p "$RAW_DIR"
mkdir -p "$DEST_DIR"
mkdir -p "$DEST_DIR/audio"
mkdir -p "$DEST_DIR/annotations/trs"
mkdir -p "$DEST_DIR/annotations/exb"
mkdir -p "$DEST_DIR/annotations/exs"
mkdir -p "$DEST_DIR/docs"

SKIP_REORG=false
if [ -d "$DEST_DIR/audio" ] && [ -d "$DEST_DIR/annotations/trs" ] && [ -d "$DEST_DIR/annotations/exb" ] && [ -d "$DEST_DIR/annotations/exs" ] && [ -d "$DEST_DIR/docs" ]; then
    if [ "$(ls -A "$DEST_DIR/audio" 2>/dev/null)" ] && [ "$(ls -A "$DEST_DIR/annotations/trs" 2>/dev/null)" ] && [ "$(ls -A "$DEST_DIR/annotations/exb" 2>/dev/null)" ] && [ "$(ls -A "$DEST_DIR/annotations/exs" 2>/dev/null)" ]; then
        echo "Dataset že organiziran; preskočim prenose/razširjanje/reorganizacijo."
        SKIP_REORG=true
    fi
fi

if [ "$SKIP_REORG" = true ]; then
    echo "=== Preskakujem prenos in reorganizacijo ==="
else
    # Prenos v data/raw
    cd "$SCRIPT_DIR/$RAW_DIR"

    echo "=== 2. Prenašam datoteke ==="
    if [ ! -f "ROG.zip" ] || [ ! -f "ROG-Art.wav.zip" ]; then
        echo "Prenašam s CLARIN.SI..."
        curl --remote-name-all https://www.clarin.si/repository/xmlui/bitstream/handle/11356/2062{/ROG.zip,/ROG-Art.wav.zip}
    else
        echo "Datoteke že obstajajo."
    fi

    echo "=== 3. Razširjam arhive v $DEST_DIR ==="
    mkdir -p "$DEST_DIR"
    unzip -q -o "ROG.zip" -d "$DEST_DIR"
    unzip -q -o "ROG-Art.wav.zip" -d "$DEST_DIR"
fi

OUTPUT_FILENAME="${1:-default_gold_standard}"
if [[ "$OUTPUT_FILENAME" != *.rttm ]]; then
    OUTPUT_FILENAME="$OUTPUT_FILENAME.rttm"
fi

echo "=== 4. Generiram gold_standard RTTM ==="
python3 "$SCRIPT_DIR/rog_art_data_process.py" --merge_threshold 1.0 --min_duration 0.1 --prioritize_pog false --output_filename "$OUTPUT_FILENAME"

# Odstranimo samo razširjene vmesne mape (struktura iz razpakiranega .zip), zip datoteke ohranimo za ponovno uporabo.
rm -rf "$RAW_DIR/data"

echo "=== 6. Končano ==="
echo "Dataset $DATASET_NAME je pripravljen v $DEST_DIR."

