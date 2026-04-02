#!/bin/bash
set -e

DATASET_NAME="CHILDES-CCPCL"
RAW_DIR="data/raw"
DEST_DIR="data/$DATASET_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== 1. Preverjam, ali je dataset že organiziran: $DATASET_NAME ==="
mkdir -p "$RAW_DIR"
mkdir -p "$DEST_DIR"
mkdir -p "$DEST_DIR/audio"
mkdir -p "$DEST_DIR/annotations/trs"
mkdir -p "$DEST_DIR/docs"

if [ ! -f "$RAW_DIR/CCPCL.zip" ]; then
    cat <<EOF
CCPCL.zip ni najden.
Za prenos sledite navodilom:
https://talkbank.org/childes/access/Slavic/Croatian/CCPCL.html

Po prijavi prenesite archív CCPCL.zip in ga postavite v:
  $RAW_DIR/CCPCL.zip

Nato ponovno zaženite:
  ./prepare_data_ccpcl.sh
EOF
    exit 1
fi

echo "=== 2. CCPCL.zip najden, nadaljujem z razširitvijo ==="

# opcijsko kratek checksum/log:
echo "CCPCL.zip: $(ls -lh "$RAW_DIR/CCPCL.zip")"

# razširimo v temp path
mkdir -p "$RAW_DIR/CCPCL"
unzip -q -o "$RAW_DIR/CCPCL.zip" -d "$RAW_DIR/CCPCL"

echo "=== 3. Razširjanje končano: $RAW_DIR/CCPCL ==="

# Izvorne datoteke v mapo data/CHILDES-CCPCL/audio (če že obstajajo iz strukture CCPCL)
# (če želite, lahko tukaj dodate samodejno kopiranje po poljubni strukturi).
# Zaenkrat le spremljanje navodila.

if [ ! -d "$DEST_DIR/audio" ]; then
    mkdir -p "$DEST_DIR/audio"
fi

wav_count=$(find "$DEST_DIR/audio" -maxdepth 2 -type f -iname "*.wav" | wc -l)

if [ "$wav_count" -gt 0 ]; then
    echo "=== Najdenih $wav_count .wav v $DEST_DIR/audio ==="
    read -rp "Želite pripraviti referenčni dataset na podlagi obstoječih WAV? [y/N]: " answer
    case "$answer" in
        [Yy]*)
            echo "Zaženem ccpcl_data_process.py ..."
            python3 "$SCRIPT_DIR/ccpcl_data_process.py" --cha_dir "$RAW_DIR/CCPCL/CCPCL" --output_file "$DEST_DIR/ref_rttm/ccpcl_gold_standard.rttm" --merge_threshold 1.0 --min_duration 0.1
            ;;
        *)
            echo "Uredi WAV datoteke v $DEST_DIR/audio in ponovno zaženi skripto, ko boš pripravljen."
            ;;
    esac
else
    cat <<EOF
=== Ni najdenih WAV v $DEST_DIR/audio ===
Za nadaljevanje prenesite zvočne datoteke iz:
https://media.talkbank.org/childes/Slavic/Croatian/CCPCL/0wav
in jih postavite v:
  $DEST_DIR/audio
Nato ponovno zaženite:
  ./prepare_data_ccpcl.sh
EOF
fi

echo "=== Konec skripte: CHILDES-CCPCL korak je izveden ==="