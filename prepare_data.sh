#!/bin/bash

# Prekini izvajanje ob napaki
set -e

# Ime dataseta - enostavno spremenljivo za prihodnje datasete
DATASET_NAME="ROG-Dialog"
BASE_DIR="data/$DATASET_NAME"

echo "=== 1. Pripravljam strukturo za dataset: $DATASET_NAME ==="
mkdir -p "$BASE_DIR/audio"
mkdir -p "$BASE_DIR/annotations/trs"
mkdir -p "$BASE_DIR/annotations/exb"
mkdir -p "$BASE_DIR/annotations/exs"
mkdir -p "$BASE_DIR/docs"
mkdir -p "$BASE_DIR/ref_rttm"  # Preimenovano v rttm
mkdir -p data/raw

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

echo "=== KONČANO! ==="
echo "Dataset $DATASET_NAME je pripravljen."