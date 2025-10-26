\
from datetime import date, datetime, timedelta
import os, re
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, IntegerField, FloatField, TextAreaField, SelectField, PasswordField
from wtforms.validators import DataRequired, Optional, Email
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from twilio.rest import Client

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_DB = f"sqlite:///{os.path.join(BASE_DIR, 'pneutrack.db')}"
DATABASE_URL = os.getenv('DATABASE_URL', DEFAULT_DB)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')

db = SQLAlchemy(app)
login_manager = LoginManager(app); login_manager.login_view = "login"

# --- MODELS ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default="admin")
    def set_password(self, raw): self.password_hash = generate_password_hash(raw)
    def check_password(self, raw): return check_password_hash(self.password_hash, raw)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(80))
    whatsapp_phone = db.Column(db.String(80))
    email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    vehicles = db.relationship('Vehicle', backref='customer', cascade="all, delete-orphan")

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    make = db.Column(db.String(80), nullable=False)
    model = db.Column(db.String(80), nullable=False)
    plate = db.Column(db.String(40), nullable=False, unique=True)
    vin = db.Column(db.String(40))
    year = db.Column(db.Integer)
    inspection_expiry = db.Column(db.Date, nullable=True)
    tires = db.relationship('TireSet', backref='vehicle', cascade="all, delete-orphan")

class TireSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    position = db.Column(db.String(40), nullable=False, default="estivo")
    brand = db.Column(db.String(80), nullable=False)
    model = db.Column(db.String(80))
    size = db.Column(db.String(40), nullable=False)
    dot = db.Column(db.String(20))
    install_date = db.Column(db.Date)
    next_change_due = db.Column(db.Date)
    front_pressure = db.Column(db.Float)
    rear_pressure = db.Column(db.Float)

class ServiceEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    plate = db.Column(db.String(40), nullable=False)
    type = db.Column(db.String(80), nullable=False)
    notes = db.Column(db.Text)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(40), nullable=False)
    type = db.Column(db.String(120), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    user_email = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- FORMS ---
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])

class CustomerForm(FlaskForm):
    name = StringField('Nome', validators=[DataRequired()])
    phone = StringField('Telefono', validators=[Optional()])
    whatsapp_phone = StringField('WhatsApp (+39...)', validators=[Optional()])
    email = StringField('Email', validators=[Optional()])
    notes = TextAreaField('Note', validators=[Optional()])

class VehicleForm(FlaskForm):
    customer_id = SelectField('Cliente', coerce=int, validators=[DataRequired()])
    make = StringField('Marca', validators=[DataRequired()])
    model = StringField('Modello', validators=[DataRequired()])
    plate = StringField('Targa', validators=[DataRequired()])
    vin = StringField('VIN', validators=[Optional()])
    year = IntegerField('Anno', validators=[Optional()])
    inspection_expiry = DateField('Scadenza Revisione', validators=[Optional()])

class TireForm(FlaskForm):
    vehicle_id = SelectField('Veicolo', coerce=int, validators=[DataRequired()])
    position = SelectField('Tipo set', choices=[('estivo','Estivo'),('invernale','Invernale'),('altro','Altro')], validators=[DataRequired()])
    brand = StringField('Brand', validators=[DataRequired()])
    model = StringField('Modello', validators=[Optional()])
    size = StringField('Misura', validators=[DataRequired()])
    dot = StringField('DOT', validators=[Optional()])
    install_date = DateField('Data montaggio', validators=[Optional()])
    next_change_due = DateField('Prossimo cambio previsto', validators=[Optional()])
    front_pressure = FloatField('Pressione anteriore (bar)', validators=[Optional()])
    rear_pressure = FloatField('Pressione posteriore (bar)', validators=[Optional()])

class EventForm(FlaskForm):
    date = DateField('Data', validators=[DataRequired()])
    plate = StringField('Targa', validators=[DataRequired()])
    type = StringField('Tipo', validators=[DataRequired()])
    notes = TextAreaField('Note', validators=[Optional()])

# --- AUTH ---
from flask_login import login_manager as _
@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

@app.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        u = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if u and u.check_password(form.password.data):
            login_user(u); return redirect(url_for('index'))
        flash('Credenziali non valide','danger')
    return render_template('login.html', form=form)

@app.route('/logout'); @login_required
def logout(): logout_user(); return redirect(url_for('login'))

# --- FILTERS & UTILS ---
@app.template_filter('d')
def fmt_date(value):
    if not value: return '-'
    return value.strftime('%d/%m/%Y')

def bootstrap_admin():
    email = os.getenv('ADMIN_EMAIL'); pwd = os.getenv('ADMIN_PASSWORD')
    if not email or not pwd: return
    if not User.query.filter_by(email=email.lower()).first():
        u = User(email=email.lower(), role='admin'); u.set_password(pwd)
        db.session.add(u); db.session.commit()

def whatsappify(phone: str):
    if not phone: return None
    p = phone.strip()
    if p.startswith('whatsapp:'): return p
    if p.startswith('+'): return f'whatsapp:{p}'
    if p.startswith('0') or p.isdigit():
        digits = re.sub(r'\\D','', p.lstrip('0')); return f'whatsapp:+39{digits}'
    return None

# --- ROUTES ---
from sqlalchemy import func
@app.route('/'); @login_required
def index():
    stats = {
        'customers': db.session.query(Customer).count(),
        'vehicles': db.session.query(Vehicle).count(),
        'tires': db.session.query(TireSet).count(),
        'events': db.session.query(ServiceEvent).count(),
    }
    return render_template('dashboard.html', stats=stats)

def customer_choices(): return [(c.id, c.name) for c in Customer.query.order_by(Customer.name.asc()).all()]
def vehicle_choices(): return [(v.id, f"{v.plate} - {v.make} {v.model}") for v in Vehicle.query.order_by(Vehicle.plate.asc()).all()]

@app.route('/customers'); @login_required
def customers():
    q = request.args.get('q','').strip(); query = Customer.query
    if q:
        like = f"%{q}%"; query = query.filter(Customer.name.ilike(like) | Customer.phone.ilike(like) | Customer.email.ilike(like))
    return render_template('customers.html', customers=query.order_by(Customer.name.asc()).all(), q=q)

@app.route('/customers/new', methods=['GET','POST']); @login_required
def customer_new():
    form = CustomerForm()
    if form.validate_on_submit():
        c = Customer(**form.data); db.session.add(c); db.session.commit(); flash('Cliente creato','success'); return redirect(url_for('customers'))
    return render_template('customer_form.html', form=form, action='Nuovo cliente')

@app.route('/customers/<int:id>/edit', methods=['GET','POST']); @login_required
def customer_edit(id):
    c = Customer.query.get_or_404(id); form = CustomerForm(obj=c)
    if form.validate_on_submit():
        form.populate_obj(c); db.session.commit(); flash('Cliente aggiornato','success'); return redirect(url_for('customers'))
    return render_template('customer_form.html', form=form, action='Modifica cliente')

@app.route('/vehicles'); @login_required
def vehicles():
    q = request.args.get('q','').strip(); query = Vehicle.query.join(Customer)
    if q:
        like = f"%{q}%"; query = query.filter((Vehicle.plate.ilike(like)) | (Vehicle.make.ilike(like)) | (Vehicle.model.ilike(like)) | (Customer.name.ilike(like)))
    return render_template('vehicles.html', vehicles=query.order_by(Vehicle.plate.asc()).all(), q=q)

@app.route('/vehicles/new', methods=['GET','POST']); @login_required
def vehicle_new():
    form = VehicleForm(); form.customer_id.choices = customer_choices()
    if form.validate_on_submit():
        v = Vehicle(**form.data); db.session.add(v); db.session.commit(); flash('Veicolo creato','success'); return redirect(url_for('vehicles'))
    return render_template('vehicle_form.html', form=form, action='Nuovo veicolo')

@app.route('/vehicles/<int:id>/edit', methods=['GET','POST']); @login_required
def vehicle_edit(id):
    v = Vehicle.query.get_or_404(id); form = VehicleForm(obj=v); form.customer_id.choices = customer_choices()
    if form.validate_on_submit():
        form.populate_obj(v); db.session.commit(); flash('Veicolo aggiornato','success'); return redirect(url_for('vehicles'))
    return render_template('vehicle_form.html', form=form, action='Modifica veicolo')

@app.route('/tires'); @login_required
def tires():
    q = request.args.get('q','').strip(); query = TireSet.query.join(Vehicle).join(Customer)
    if q:
        like = f"%{q}%"; query = query.filter((Vehicle.plate.ilike(like)) | (TireSet.brand.ilike(like)) | (TireSet.model.ilike(like)) | (TireSet.size.ilike(like)) | (Customer.name.ilike(like)))
    return render_template('tires.html', tires=query.order_by(TireSet.install_date.desc().nullslast()).all(), q=q)

@app.route('/tires/new', methods=['GET','POST']); @login_required
def tire_new():
    form = TireForm(); form.vehicle_id.choices = vehicle_choices()
    if form.validate_on_submit():
        t = TireSet(**form.data); db.session.add(t); db.session.commit(); flash('Set gomme creato','success'); return redirect(url_for('tires'))
    return render_template('tire_form.html', form=form, action='Nuovo set gomme')

@app.route('/tires/<int:id>/edit', methods=['GET','POST']); @login_required
def tire_edit(id):
    t = TireSet.query.get_or_404(id); form = TireForm(obj=t); form.vehicle_id.choices = vehicle_choices()
    if form.validate_on_submit():
        form.populate_obj(t); db.session.commit(); flash('Set gomme aggiornato','success'); return redirect(url_for('tires'))
    return render_template('tire_form.html', form=form, action='Modifica set gomme')

@app.route('/events', methods=['GET','POST']); @login_required
def events():
    form = EventForm()
    if form.validate_on_submit():
        e = ServiceEvent(**form.data); db.session.add(e); db.session.commit(); flash('Evento registrato','success'); return redirect(url_for('events'))
    data = ServiceEvent.query.order_by(ServiceEvent.date.desc()).all()
    return render_template('events.html', events=data, form=form)

@app.route('/documents'); @login_required
def documents():
    from models import Document as _  # placeholder if modularized later
    docs = Document.query.order_by(Document.created_at.desc()).all()
    return render_template('documents.html', docs=docs)

@app.route('/documents/upload', methods=['POST']); @login_required
def documents_upload():
    f = request.files.get('file'); plate = request.form.get('plate','').strip().upper(); dtype = request.form.get('type','Altro documento')
    if not f or not plate: flash('Compila tutti i campi e seleziona un file','danger'); return redirect(url_for('documents'))
    fname = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{plate}_{f.filename}")
    f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
    d = Document(plate=plate, type=dtype, filename=fname, user_email=current_user.email); db.session.add(d); db.session.commit()
    flash('Documento caricato','success'); return redirect(url_for('documents'))

@app.route('/uploads/<path:filename>'); @login_required
def uploads(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def build_messages_for_day(target_day: date):
    msgs = []; soon = target_day + timedelta(days=15)
    vehicles_due = Vehicle.query.filter(Vehicle.inspection_expiry == soon).all()
    for v in vehicles_due:
        c = v.customer; to_wh = whatsappify(c.whatsapp_phone or c.phone); to_sms = (c.phone or '').strip()
        body = f"Ciao {c.name}, revisione per {v.make} {v.model} ({v.plate}) in scadenza il {soon.strftime('%d/%m/%Y')}. Prenota in Carrozzeria Moglianese."
        msgs.append({'type':'revisione','channel':'whatsapp' if to_wh else 'sms','to':to_wh or to_sms,'date':soon,'body':body})
    tire_due = db.session.query(TireSet, Vehicle, Customer).join(Vehicle).join(Customer).filter(TireSet.next_change_due == soon).all()
    for t, v, c in tire_due:
        to_wh = whatsappify(c.whatsapp_phone or c.phone); to_sms = (c.phone or '').strip()
        body = f"Ciao {c.name}, promemoria cambio gomme ({t.position}) per {v.make} {v.model} ({v.plate}) il {soon.strftime('%d/%m/%Y')}. Vuoi fissare?"
        msgs.append({'type':'gomme','channel':'whatsapp' if to_wh else 'sms','to':to_wh or to_sms,'date':soon,'body':body})
    return msgs

@app.route('/notifications/preview'); @login_required
def notifications_preview():
    today = date.today(); token = request.args.get('token',''); msgs = build_messages_for_day(today)
    return render_template('notifications_preview.html', today=today, msgs=msgs, token=token)

@app.route('/notifications/run', methods=['POST']); @login_required
def notifications_run():
    token = request.args.get('token') or request.headers.get('X-Notify-Token')
    if token != os.getenv('NOTIFY_TOKEN',''): return "Unauthorized", 401
    msgs = build_messages_for_day(date.today())
    sid = os.getenv('TWILIO_ACCOUNT_SID'); auth = os.getenv('TWILIO_AUTH_TOKEN')
    wfrom = os.getenv('TWILIO_WHATSAPP_FROM',''); sfrom = os.getenv('TWILIO_SMS_FROM','')
    if not (sid and auth and (wfrom or sfrom)): flash('Config Twilio mancante: TWILIO_*','danger'); return redirect(url_for('notifications_preview'))
    client = Client(sid, auth); sent=0; errors=0
    for m in msgs:
        try:
            if m['channel']=='whatsapp' and wfrom: client.messages.create(from_=wfrom, to=m['to'], body=m['body']); sent+=1
            elif m['channel']=='sms' and sfrom: client.messages.create(from_=sfrom, to=m['to'], body=m['body']); sent+=1
        except Exception as e: errors+=1; print('Errore invio:', e)
    flash(f'Inviati {sent} messaggi, errori {errors}','success' if errors==0 else 'warning'); return redirect(url_for('notifications_preview'))

@app.route('/cron/daily')
def cron_daily():
    token = request.args.get('token')
    if token != os.getenv('NOTIFY_TOKEN',''): return "Unauthorized", 401
    sid = os.getenv('TWILIO_ACCOUNT_SID'); auth = os.getenv('TWILIO_AUTH_TOKEN')
    wfrom = os.getenv('TWILIO_WHATSAPP_FROM',''); sfrom = os.getenv('TWILIO_SMS_FROM','')
    if not (sid and auth and (wfrom or sfrom)): return "Twilio not configured", 200
    msgs = build_messages_for_day(date.today()); client = Client(sid, auth); sent=0
    for m in msgs:
        try:
            if m['channel']=='whatsapp' and wfrom: client.messages.create(from_=wfrom, to=m['to'], body=m['body']); sent+=1
            elif m['channel']=='sms' and sfrom: client.messages.create(from_=sfrom, to=m['to'], body=m['body']); sent+=1
        except Exception as e: print('Errore invio cron:', e)
    return f"Sent {sent}", 200

@app.route('/healthz')
def healthz(): return "ok", 200

@login_manager.user_loader
def _load(uid): return User.query.get(int(uid))

@app.context_processor
def inject_now(): return {'now': datetime.now()}

def bootstrap():
    with app.app_context():
        db.create_all(); bootstrap_admin(); os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

if __name__ == '__main__':
    bootstrap(); app.run(host="0.0.0.0", port=int(os.getenv('PORT', 5000)), debug=True)
@app.route('/healthz')
def healthz():
    return "ok", 200
