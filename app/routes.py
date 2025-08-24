from app import app
from flask import Flask, flash, render_template, redirect, url_for, Response, request, g
from app.forms import JobForm, AlertForm, LoginForm
from app.simulator import start_simulation
from app.models import User, auth_db
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from functools import wraps
from datetime import datetime, timedelta
from pymongo import MongoClient
import os
from datetime import datetime
import json
import time
import uuid

# ------------------ Auth Helpers ------------------

def operator_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.userType != 'operator':
            flash("Access denied for non-operators", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.userType != 'manager':
            flash("Access denied for non-managers", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ------------------ DB Helpers ------------------
lathe_maintenance = {}

def get_db():
    if 'mongo_client' not in g:
        g.mongo_client = MongoClient(os.getenv('MONGO_URI'))
    return g.mongo_client

def get_collections(machine_id):
    machine_num = int(machine_id.split('-')[1])
    client = get_db()  # ✅ use the correct function name
    return {
        'jobs': client['Jobs'][f'lathe{machine_num}_job_detail'],
        'sensor': client['SensorData'][f'lathe{machine_num}_sensory_data'],
        'alerts': client['Alerts'][f'lathe{machine_num}_alerts']
    }

@app.teardown_appcontext
def close_db(error):
    if 'db' in g:
        g.db.close()
# ------------------ Debug mongodb ------------------
@app.route('/debug/mongodb')
@login_required
def debug_mongodb():
    try:
        db = get_db()
        # Test connection
        collections = db.list_database_names()
        return f"✅ MongoDB Connected! Databases: {collections}"
    except Exception as e:
        return f"❌ MongoDB Connection Failed: {str(e)}"

# ------------------ Auth Routes ------------------

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        record = auth_db.users.find_one({"userID": form.userID.data})
        if record and check_password_hash(record['passwordHash'], form.password.data or ""):
            user = User(record['_id'], record['employeeId'], record['userID'], record['userType'])
            login_user(user)
            auth_db.users.update_one({'_id': record['_id']}, {'$set': {'lastLogin': datetime.now()}})
            return redirect(url_for('manager_landing') if user.userType == "manager" else 'dashboard')
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/home')
@login_required
def home_redirect():
    return redirect(url_for('manager_landing') if current_user.userType == 'manager' else 'dashboard')

# ------------------ Manager View ------------------

@app.route('/manager')
@login_required
@manager_required
def manager_landing():
    return render_template('manager_landing.html')

# @app.route('/analytics')
# @login_required
# @manager_required
# def analytics_dashboard():
#     db = get_db()
#     lathe_jobs = []
#     lathe_rpm = []
#     lathe_temp = []
#     lathe_power = []

#     total_jobs = 0
#     active_jobs = 0

#     for machine_num in range(1, 21):
#         job_coll = db['Jobs'][f'lathe{machine_num}_job_detail']
#         sensor_coll = db['SensorData'][f'lathe{machine_num}_sensory_data']

#         # Count jobs
#         jobs_count = job_coll.count_documents({})
#         lathe_jobs.append(jobs_count)
#         total_jobs += jobs_count

#         active_jobs += job_coll.count_documents({'status': 'ongoing'})

#         # Compute averages (defensive handling in case of no data)
#         try:
#             rpm = sensor_coll.aggregate([
#                 {"$group": {"_id": None, "avg": {"$avg": "$rpm"}}}
#             ])
#             lathe_rpm.append(round(next(rpm, {}).get('avg', 0), 2))
#         except:
#             lathe_rpm.append(0)

#         try:
#             temp = sensor_coll.aggregate([
#                 {"$group": {"_id": None, "avg": {"$avg": "$temperature"}}}
#             ])
#             lathe_temp.append(round(next(temp, {}).get('avg', 0), 2))
#         except:
#             lathe_temp.append(0)

#         try:
#             power = sensor_coll.aggregate([
#                 {"$group": {"_id": None, "avg": {"$avg": "$powerConsumption"}}}
#             ])
#             lathe_power.append(round(next(power, {}).get('avg', 0), 2))
#         except:
#             lathe_power.append(0)

#    return render_template(
#     "analytics_dashboard.html",
#     lathe_jobs=lathe_jobs,
#     lathe_rotationalSpeed=lathe_rotationalSpeed,
#     lathe_airTemperature=lathe_airTemperature,
#     lathe_processTemperature=lathe_processTemperature,
#     lathe_torque=lathe_torque,
#     lathe_toolWear=lathe_toolWear
# )
@app.route('/analytics')
@login_required
@manager_required
def analytics_dashboard():
    db = get_db()
    lathe_jobs = []
    lathe_rotationalSpeed = []   # was lathe_rpm
    lathe_airTemperature = []    # was lathe_temp
    lathe_processTemperature = []  # if you track separately
    lathe_torque = []            # new metric
    lathe_toolWear = []          # new metric

    total_jobs = 0
    active_jobs = 0

    for machine_num in range(1, 21):
        job_coll = db['Jobs'][f'lathe{machine_num}_job_detail']
        sensor_coll = db['SensorData'][f'lathe{machine_num}_sensory_data']

        # Count jobs
        jobs_count = job_coll.count_documents({})
        lathe_jobs.append(jobs_count)
        total_jobs += jobs_count
        active_jobs += job_coll.count_documents({'status': 'ongoing'})

        # 🔥 FIXED - Using correct parameter names
        try:
            rpm = sensor_coll.aggregate([
                {"$group": {"_id": None, "avg": {"$avg": "$rotationalSpeed"}}}  # ✅ Fixed
            ])
            lathe_rotationalSpeed.append(round(next(rpm, {}).get('avg', 0), 2))
        except:
            lathe_rotationalSpeed.append(0)

        try:
            air_temp = sensor_coll.aggregate([
                {"$group": {"_id": None, "avg": {"$avg": "$airTemperature"}}}
            ])
            lathe_airTemperature.append(round(next(air_temp, {}).get('avg', 0), 2))
        except:
            lathe_airTemperature.append(0)

        try:
            process_temp = sensor_coll.aggregate([
                {"$group": {"_id": None, "avg": {"$avg": "$processTemperature"}}}
            ])
            lathe_processTemperature.append(round(next(process_temp, {}).get('avg', 0), 2))
        except:
            lathe_processTemperature.append(0)

        try:
            torque = sensor_coll.aggregate([
                {"$group": {"_id": None, "avg": {"$avg": "$torque"}}}
            ])
            lathe_torque.append(round(next(torque, {}).get('avg', 0), 2))
        except:
            lathe_torque.append(0)

        try:
            tool_wear = sensor_coll.aggregate([
                {"$group": {"_id": None, "avg": {"$avg": "$toolWear"}}}
            ])
            lathe_toolWear.append(round(next(tool_wear, {}).get('avg', 0), 2))
        except:
            lathe_toolWear.append(0)

    return render_template(
        "analytics_dashboard.html",
        lathe_jobs=lathe_jobs,
        lathe_rotationalSpeed=lathe_rotationalSpeed,
        lathe_airTemperature=lathe_airTemperature,
        lathe_processTemperature=lathe_processTemperature,
        lathe_torque=lathe_torque,
        lathe_toolWear=lathe_toolWear,
        total_jobs=total_jobs,
        active_jobs=active_jobs
    )



# ------------------ Lathe Dashboard ------------------

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    active_machines = []
    lathe_statuses = []
    now = datetime.utcnow()

    for machine_num in range(1, 21):
        machine_id = f"LATHE-{machine_num:02d}"
        job_coll = db['Jobs'][f'lathe{machine_num}_job_detail']
        is_on = bool(job_coll.find_one({"status": "ongoing"}))

        # Dummy in-memory maintenance check
        maintenance = lathe_maintenance.get(machine_id)
        under_maintenance = False
        if maintenance and maintenance['start'] <= now <= maintenance['end']:
            under_maintenance = True
        elif maintenance and now > maintenance['end']:
            del lathe_maintenance[machine_id]  # Clean expired

        lathe_statuses.append({
            'id': machine_id,
            'is_on': is_on,
            'under_maintenance': under_maintenance
        })

    total_lathes = 20
    on_count = sum(1 for lathe in lathe_statuses if lathe['is_on'])
    off_count = total_lathes - on_count

    return render_template(
        'dashboard.html',
        lathe_statuses=lathe_statuses,
        total_lathes=total_lathes,
        on_count=on_count,
        off_count=off_count
    )


# ------------------ Lathe Control & Monitoring ------------------

@app.route('/lathe/<machine_id>', methods=['GET', 'POST'])
@login_required
def lathe_detail(machine_id):
    collections = get_collections(machine_id)
    alert_form = AlertForm()

    now = datetime.utcnow()
    maintenance = lathe_maintenance.get(machine_id)
    under_maintenance = False
    if maintenance and maintenance['start'] <= now <= maintenance['end']:
        under_maintenance = True
    elif maintenance and now > maintenance['end']:
        del lathe_maintenance[machine_id]

    if alert_form.validate_on_submit():
        collections['alerts'].insert_one({
            "machineId": machine_id,
            "timestamp": datetime.utcnow(),
            "message": alert_form.message.data,
            "status": "active"
        })
        flash('Alert created successfully!', 'success')
        return redirect(url_for('lathe_detail', machine_id=machine_id))

    current_job = collections['jobs'].find_one({"status": "ongoing"})
    sensor_data = collections['sensor'].find_one(sort=[("timestamp", -1)])

    return render_template('lathe_detail.html',
        machine_id=machine_id,
        current_job=current_job,
        sensor_data=sensor_data,
        alert_form=alert_form,
        under_maintenance=under_maintenance
    )


@app.route('/lathe/<machine_id>/start', methods=['GET', 'POST'])
@login_required
@operator_required
def start_simulator(machine_id):
    collections = get_collections(machine_id)
    form = JobForm()

    if form.validate_on_submit():
        job_id = str(uuid.uuid4())
        print(f"🎯 Creating job {job_id} for {machine_id}")  # Debug
        
        job_data = {
            "_id": job_id,
            "machineId": machine_id,
            "operatorId": form.operator_name.data,
            "jobId": job_id,
            "jobType": form.job_type.data,
            "jobDescription": form.job_description.data,
            "startTime": datetime.utcnow(),
            "status": "ongoing",
            "estimatedTime": form.estimated_time.data,
            "actualDuration": 0
        }

        collections['jobs'].insert_one(job_data)
        print(f"✅ Job inserted into database")  # Debug
        
        start_simulation(
            machine_id=machine_id,
            job_id=job_id,
            duration=form.estimated_time.data,
            material=form.material.data,
            job_type=form.job_type.data,
            tool_no=form.tool_no.data
        )
        print(f"🚀 Simulation thread started")  # Debug
        
        flash('Simulation started successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('simulator_form.html', form=form, machine_id=machine_id)


@app.route('/lathe/<machine_id>/jobs')
@login_required
def job_history(machine_id):
    collections = get_collections(machine_id)
    jobs = list(collections['jobs'].find(sort=[("startTime", -1)]))
    return render_template('jobs.html', jobs=jobs, machine_id=machine_id)

@app.route('/lathe/<machine_id>/alerts', methods=['GET'])
@login_required
def alert_history(machine_id):
    collections = get_collections(machine_id)
    alerts = list(collections['alerts'].find(sort=[("timestamp", -1)]))
    return render_template('alerts.html', alerts=alerts, machine_id=machine_id)

@app.route('/lathe/<machine_id>/alerts', methods=['POST'])
@login_required
def handle_alert(machine_id):
    collections = get_collections(machine_id)
    alert_form = AlertForm()

    if alert_form.validate_on_submit():
        collections['alerts'].insert_one({
            "machineId": machine_id,
            "timestamp": datetime.utcnow(),
            "alertType": "General",
            "severity": 3,
            "message": alert_form.message.data,
            "status": "active"
        })
        return '''
        <script>
            window.close();
            if(window.opener && !window.opener.closed) {
                window.opener.location.reload();
            }
        </script>
        '''
    return render_template('alert_form.html', alert_form=alert_form, machine_id=machine_id)

@app.route('/lathe/<machine_id>/add_alert', methods=['GET'])
@login_required
def add_alert(machine_id):
    alert_form = AlertForm()
    return render_template('alert_form.html', alert_form=alert_form, machine_id=machine_id)

@app.route('/lathe/<machine_id>/maintenance')
@login_required
@manager_required
def schedule_maintenance(machine_id):
    # Schedule maintenance for 10 minutes
    lathe_maintenance[machine_id] = {
        "start": datetime.utcnow(),
        "end": datetime.utcnow() + timedelta(minutes=10)
    }
    flash(f"{machine_id} scheduled for maintenance.", "info")
    return redirect(url_for('lathe_detail', machine_id=machine_id))

@app.route('/lathe/<machine_id>/status')
@login_required
def current_status(machine_id):
    collections = get_collections(machine_id)
    current_job = collections['jobs'].find_one({"status": "ongoing"})
    sensor_data = collections['sensor'].find_one(sort=[("timestamp", -1)])
    return render_template('status.html',
        current_job=current_job,
        sensor_data=sensor_data,
        machine_id=machine_id
    )

@app.route('/simulation/status/<machine_id>')
@login_required
def simulation_status(machine_id):
    collections = get_collections(machine_id)

    def generate():
        while True:
            last_data = collections['sensor'].find_one(sort=[("timestamp", -1)])
            current_job = collections['jobs'].find_one({"status": "ongoing"})

            data = {"status": "completed"}
            if last_data and current_job:
                data.update({
    "airTemperature": last_data.get("airTemperature", 0),
    "processTemperature": last_data.get("processTemperature", 0),
    "rotationalSpeed": last_data.get("rotationalSpeed", 0),
    "torque": last_data.get("torque", 0),
    "toolWear": last_data.get("toolWear", 0),
    "failureProbability": last_data.get("failureProbability", 0),
    "status": "running"
})


            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(1)

    return Response(generate(), mimetype="text/event-stream")
