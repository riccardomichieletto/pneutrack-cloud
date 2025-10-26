from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
from datetime import datetime
import os

# -----------------------------
# CONFIGURAZIONE BASE APP
# -----------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# --- DATABASE CONFIG (con fix SSL per Render) ---
uri = os.environ.get("DATABASE_URL", "sqlite:///local.db")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {"sslmode": "require"}  # forza connessione sicura
}

db = SQLAlchemy(app)

# -----------------------------
# MODELLI DATABASE
# -----------------------------
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20), nullable=False)
    brand = db.Column(db.String(50))
    model = db.Column(db.String(50))
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client = db.relationship("Client", backref=db.backref("vehicles", lazy=True))

class TireSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.String(50))
    brand = db.Column(db.String(50))
    season = db.Column(db.String(20))
    stored = db.Column(db.Boolean, default=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicle.id"))
    vehicle = db.relationship("Vehicle", backref=db.backref("tires", lazy=True))

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    expire_date = db.Column(db.Date)
    user = db.Column(db.String(100))

# -----------------------------
# UTILITY: assicurati che le tabelle esistano
# -----------------------------
def ensure_tables():
    """Crea le tabelle se non esistono (utile al primo avvio su Render)."""
    insp = inspect(db.engine)
    needed = {"client", "vehicle", "tire_set", "document"}
    existing = set(insp.get_table_names())
    if not needed.issubset(existing):
        db.create_all()

# crea anche all'import (avvio Gunicorn)
with app.app_context():
    ensure_tables()

# -----------------------------
# ROUTES PRINCIPALI
# -----------------------------
@app.route("/")
def index():
    try:
        # doppia sicurezza: crea se mancano anche al primo GET
        ensure_tables()
        clients = Client.query.order_by(Client.name).all()
        # pagina minimale temporanea
        items = "<br>".join([f"- {c.name} ({c.phone or '-'})" for c in clients]) or "Nessun cliente ancora."
        return f"<h1>PneuTrack Cloud – Carrozzeria Moglianese</h1><p>{items}</p>", 200
    except Exception as e:
        return f"Errore durante il caricamento: {e}", 500

@app.route("/add_client", methods=["POST"])
def add_client():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone")
    email = request.form.get("email")
    notes = request.form.get("notes")
    if not name:
        flash("Nome obbligatorio", "danger")
        return redirect(url_for("index"))
    db.session.add(Client(name=name, phone=phone, email=email, notes=notes))
    db.session.commit()
    flash("Cliente aggiunto!", "success")
    return redirect(url_for("index"))

@app.route("/delete_client/<int:id>")
def delete_client(id):
    client = Client.query.get_or_404(id)
    db.session.delete(client)
    db.session.commit()
    flash("Cliente eliminato!", "warning")
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    flash("Logout effettuato", "info")
    return redirect(url_for("index"))

# -----------------------------
# HEALTH CHECK
# -----------------------------
@app.route("/healthz")
def healthz():
    return "OK", 200

# -----------------------------
# AVVIO APP (solo locale)
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
