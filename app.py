from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
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

# Crea le tabelle anche su Render (non solo in locale)
with app.app_context():
    db.create_all()


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
# ROUTES PRINCIPALI
# -----------------------------
@app.route("/")
def index():
    try:
        clients = Client.query.order_by(Client.name).all()
        return render_template("index.html", clients=clients)
    except Exception as e:
        return f"Errore durante il caricamento: {e}", 500


@app.route("/add_client", methods=["POST"])
def add_client():
    name = request.form["name"]
    phone = request.form["phone"]
    email = request.form["email"]
    notes = request.form["notes"]

    new_client = Client(name=name, phone=phone, email=email, notes=notes)
    db.session.add(new_client)
    db.session.commit()
    flash("Cliente aggiunto con successo!", "success")
    return redirect(url_for("index"))


@app.route("/delete_client/<int:id>")
def delete_client(id):
    client = Client.query.get_or_404(id)
    db.session.delete(client)
    db.session.commit()
    flash("Cliente eliminato!", "danger")
    return redirect(url_for("index"))


@app.route("/add_vehicle/<int:client_id>", methods=["POST"])
def add_vehicle(client_id):
    plate = request.form["plate"]
    brand = request.form["brand"]
    model = request.form["model"]
    new_vehicle = Vehicle(plate=plate, brand=brand, model=model, client_id=client_id)
    db.session.add(new_vehicle)
    db.session.commit()
    flash("Veicolo aggiunto!", "success")
    return redirect(url_for("index"))


@app.route("/add_doc", methods=["POST"])
def add_doc():
    name = request.form["name"]
    expire_date = request.form["expire_date"]
    user = request.form["user"]
    new_doc = Document(name=name, expire_date=expire_date, user=user)
    db.session.add(new_doc)
    db.session.commit()
    flash("Documento aggiunto!", "success")
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
