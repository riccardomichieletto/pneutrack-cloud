from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

# ----------------------------------------------------------------------------
# CONFIGURAZIONE BASE
# ----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# Correzione URL PostgreSQL per Render
uri = os.environ.get("DATABASE_URL", "sqlite:///local.db")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ----------------------------------------------------------------------------
# MODELLI DATABASE
# ----------------------------------------------------------------------------
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20), nullable=False)
    make = db.Column(db.String(50))
    model = db.Column(db.String(50))
    year = db.Column(db.String(10))
    inspection = db.Column(db.String(20))
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client = db.relationship("Client", backref=db.backref("vehicles", lazy=True))

class TireSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20))
    set_type = db.Column(db.String(20))   # estivo / invernale
    brand = db.Column(db.String(50))
    size = db.Column(db.String(50))
    dot = db.Column(db.String(10))
    front_pressure = db.Column(db.Float)
    rear_pressure = db.Column(db.Float)
    next_change = db.Column(db.String(20))

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20))
    doc_type = db.Column(db.String(50))
    date = db.Column(db.String(20))
    expires = db.Column(db.String(20))
    user = db.Column(db.String(50))

# ----------------------------------------------------------------------------
# ROUTES (PAGINE)
# ----------------------------------------------------------------------------
@app.route("/")
def index():
    clients = Client.query.order_by(Client.name).all()
    vehicles = Vehicle.query.order_by(Vehicle.plate).all()
    tires = TireSet.query.order_by(TireSet.plate).all()
    docs = Document.query.order_by(Document.date.desc()).all()
    return render_template("dashboard.html", clients=clients, vehicles=vehicles, tires=tires, docs=docs)

@app.route("/add_client", methods=["POST"])
def add_client():
    name = request.form.get("name")
    phone = request.form.get("phone")
    email = request.form.get("email")
    if not name:
        flash("Il nome è obbligatorio.", "danger")
        return redirect(url_for("index"))
    new_client = Client(name=name, phone=phone, email=email)
    db.session.add(new_client)
    db.session.commit()
    flash("Cliente aggiunto con successo.", "success")
    return redirect(url_for("index"))

@app.route("/add_vehicle", methods=["POST"])
def add_vehicle():
    plate = request.form.get("plate")
    make = request.form.get("make")
    model = request.form.get("model")
    year = request.form.get("year")
    inspection = request.form.get("inspection")
    client_id = request.form.get("client_id")
    if not plate:
        flash("La targa è obbligatoria.", "danger")
        return redirect(url_for("index"))
    new_vehicle = Vehicle(plate=plate, make=make, model=model, year=year, inspection=inspection, client_id=client_id)
    db.session.add(new_vehicle)
    db.session.commit()
    flash("Veicolo aggiunto con successo.", "success")
    return redirect(url_for("index"))

@app.route("/add_tire", methods=["POST"])
def add_tire():
    plate = request.form.get("plate")
    set_type = request.form.get("set_type")
    brand = request.form.get("brand")
    size = request.form.get("size")
    dot = request.form.get("dot")
    front = request.form.get("front_pressure")
    rear = request.form.get("rear_pressure")
    next_change = request.form.get("next_change")
    new_tire = TireSet(plate=plate, set_type=set_type, brand=brand, size=size, dot=dot,
                       front_pressure=front, rear_pressure=rear, next_change=next_change)
    db.session.add(new_tire)
    db.session.commit()
    flash("Set gomme salvato correttamente.", "success")
    return redirect(url_for("index"))

@app.route("/add_doc", methods=["POST"])
def add_doc():
    plate = request.form.get("plate")
    doc_type = request.form.get("doc_type")
    date = request.form.get("date")
    expires = request.form.get("expires")
    user = request.form.get("user")
    new_doc = Document(plate=plate, doc_type=doc_type, date=date, expires=expires, user=user)
    db.session.add(new_doc)
    db.session.commit()
    flash("Documento salvato.", "success")
    return redirect(url_for("index"))

@app.route('/logout')
def logout():
    return "logout ok", 200

# ----------------------------------------------------------------------------
# HEALTHCHECK PER RENDER
# ----------------------------------------------------------------------------
@app.route('/healthz')
def healthz():
    return "ok", 200

# ----------------------------------------------------------------------------
# AVVIO APP
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
