# Uporabimo isto preverjeno osnovo za GB10 (Grace Blackwell)
FROM nvcr.io/nvidia/pytorch:25.09-py3

WORKDIR /app

# 1. Izklop bufferinga
ENV PYTHONUNBUFFERED=1

# 2. Sistemske knjižnice (NeMo rabi Cython in specifične libsndfile headerje)
RUN apt-get update && apt-get install -y \
    libsndfile1 ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

# 3. Priprava okolja za NeMo
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir Cython packaging

# 4. Namestitev NeMo Toolkit (samo ASR modul, ki vsebuje diarizacijo)
# To bo potegnilo kar nekaj odvisnosti.
RUN pip install --no-cache-dir "nemo_toolkit[asr]"

# 5. HuggingFace Hub za prenos modelov
RUN pip install --no-cache-dir huggingface_hub soundfile

# Kopiranje skripte
COPY run_inference.py .

ENTRYPOINT ["python", "run_inference.py"]