# PneuTrack Cloud — Carrozzeria Moglianese
Deploy immediato su Render: usa il file `render.yaml` (Blueprint).

## Avvio locale
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.sample .env
python app.py
