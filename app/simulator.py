from threading import Thread
from pymongo import MongoClient
import random
import time
import os
from datetime import datetime
import pickle
import numpy as np

# Load ML model with better error handling
MODEL_PATH = os.getenv('ML_MODEL_PATH', 'model.pkl')
ml_model = None


print("=" * 50)
print("SIMULATOR INITIALIZATION")
print("=" * 50)

# Try multiple paths for the ML model
model_paths = ['model.pkl', 'app/model.pkl', os.path.join(os.getcwd(), 'model.pkl')]

for path in model_paths:
    try:
        if os.path.exists(path):
            print(f"Found model file at: {path}")
            with open(path, 'rb') as f:
                ml_model = pickle.load(f)
            print(f"✅ ML model loaded successfully from {path}")
            break
        else:
            print(f"Model file not found at: {path}")
    except Exception as e:
        print(f"❌ Error loading model from {path}: {str(e)}")

if ml_model is None:
    print("⚠️ No ML model loaded - will use random failure probability")

# Material properties database (typical values)
MATERIAL_PROFILES = {
    'Mild Steel': {
        'hardness': 120,
        'thermal_conductivity': 50,
        'specific_heat': 460,
        'base_air_temp': 298,
        'process_temp_multiplier': 1.8,
        'torque_factor': 1.2
    },
    'Aluminum': {
        'hardness': 35,
        'thermal_conductivity': 237,
        'specific_heat': 900,
        'base_air_temp': 295,
        'process_temp_multiplier': 1.4,
        'torque_factor': 0.8
    },
    'Wood': {
        'hardness': 2,
        'thermal_conductivity': 0.12,
        'specific_heat': 1700,
        'base_air_temp': 293,
        'process_temp_multiplier': 1.1,
        'torque_factor': 0.3
    }
}

TOOL_WEAR_RATES = {
    'Mild Steel': 0.25,
    'Aluminum': 0.15,
    'Wood': 0.05
}

def calculate_machine_parameters(material, job_type, tool_diameter):
    base_rpm = {
        'Mild Steel': random.randint(800, 1200),
        'Aluminum': random.randint(1500, 2500),
        'Wood': random.randint(2800, 3500)
    }[material]

    base_torque_ranges = {
        'turning': (15, 25),
        'facing': (20, 35),
        'threading': (10, 20),
        'drilling': (25, 45),
        'boring': (18, 30),
        'knurling': (12, 22)
    }

    torque_range = base_torque_ranges[job_type]
    base_torque = random.uniform(torque_range[0], torque_range[1]) * \
                  MATERIAL_PROFILES[material]['torque_factor'] * (tool_diameter / 10)
    return base_rpm, base_torque

def generate_sensor_data(machine_id, job_id, duration, material, job_type, tool_no):
    client = None
    jobs_collection = None
    start_time = None
    
    print(f"🚀 Starting simulation for {machine_id}, Job: {job_id}")
    
    try:
        client = MongoClient(os.getenv('MONGO_URI'))
        print(f"✅ Connected to MongoDB")
        
        machine_number = int(machine_id.split('-')[1])
        jobs_collection = client['Jobs'][f'lathe{machine_number}_job_detail']
        sensor_collection = client['SensorData'][f'lathe{machine_number}_sensory_data']

        tool_diameter = 10 + tool_no * 2
        base_rpm, base_torque = calculate_machine_parameters(material, job_type, tool_diameter)
        material_props = MATERIAL_PROFILES[material]

        duration_seconds = duration * 60
        start_time = time.time()
        end_time = start_time + duration_seconds

        # Update job details
        job_update_result = jobs_collection.update_one(
            {"_id": job_id},
            {"$set": {
                "machineId": machine_id,
                "jobId": job_id,
                "jobType": job_type,
                "startTime": datetime.utcnow(),
                "status": "ongoing",
                "estimatedTime": duration
            }},
            upsert=True
        )
        print(f"✅ Job document updated: {job_update_result.modified_count} modified, {job_update_result.upserted_id}")

        data_points_inserted = 0
        
        while time.time() < end_time:
            elapsed = (time.time() - start_time) / 60

            # Tool wear in minutes
            tool_wear_minutes = min(duration * 0.8, TOOL_WEAR_RATES[material] * elapsed)

            # RPM with wear effect
            wear_factor = 1 - (tool_wear_minutes / (duration * 2))
            current_rpm = base_rpm * wear_factor * random.normalvariate(1, 0.03)
            current_rpm = max(100, current_rpm)

            # Torque with wear effect
            torque_increase_factor = 1 + (tool_wear_minutes / duration) * 0.4
            current_torque = base_torque * torque_increase_factor * random.normalvariate(1, 0.08)
            current_torque = max(5, current_torque)

            # Air temperature (K)
            air_temp_k = material_props['base_air_temp'] + random.normalvariate(0, 3)
            air_temp_k = max(273, min(air_temp_k, 313))

            # Process temperature (K)
            process_temp_base = air_temp_k * material_props['process_temp_multiplier']
            machining_heat = (current_torque * current_rpm / 1000) * 15
            wear_heat = tool_wear_minutes * 8
            process_temp_k = process_temp_base + machining_heat + wear_heat + random.normalvariate(0, 10)
            process_temp_k = max(air_temp_k + 50, min(process_temp_k, 1073))

            # ML Prediction with safe handling
            if ml_model is not None:
                try:
                    features = np.array([[air_temp_k, process_temp_k, current_rpm, current_torque, tool_wear_minutes]])
                    failure_prob = ml_model.predict_proba(features)[0][1]
                except Exception as ml_error:
                    print(f"⚠️ ML prediction error: {ml_error}")
                    failure_prob = random.uniform(0.0, 0.3)  # Fallback random value
            else:
                failure_prob = random.uniform(0.0, 0.3)  # Random failure probability when no model

            sensor_data = {
                "machineId": machine_id,
                "jobId": job_id,
                "timestamp": datetime.utcnow(),
                "airTemperature": round(air_temp_k, 2),
                "processTemperature": round(process_temp_k, 2),
                "rotationalSpeed": round(current_rpm, 1),
                "torque": round(current_torque, 2),
                "toolWear": round(tool_wear_minutes, 2),
                "failureProbability": float(failure_prob)
            }

            insert_result = sensor_collection.insert_one(sensor_data)
            data_points_inserted += 1
            
            if data_points_inserted % 5 == 0:  # Print every 5th insertion
                print(f"📊 Inserted {data_points_inserted} sensor data points for {machine_id}")

            remaining = end_time - time.time()
            if remaining > 0:
                time.sleep(min(5, remaining))

        print(f"✅ Simulation completed for {job_id}. Total data points: {data_points_inserted}")

    except Exception as e:
        print(f"❌ Simulation error for {job_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if jobs_collection is not None:
            jobs_collection.update_one(
                {"_id": job_id},
                {"$set": {"status": "failed", "error": str(e)}}
            )
    finally:
        # Always mark job as completed
        if jobs_collection is not None:
            try:
                actual_duration = None
                if start_time:
                    actual_duration = round((time.time() - start_time) / 60, 2)
                
                completion_result = jobs_collection.update_one(
                    {"_id": job_id},
                    {"$set": {
                        "status": "completed",
                        "endTime": datetime.utcnow(),
                        "actualDuration": actual_duration
                    }}
                )
                print(f"✅ Job {job_id} marked as completed")
            except Exception as e:
                print(f"❌ Failed to mark job as completed: {str(e)}")
        
        if client:
            client.close()

def start_simulation(machine_id, job_id, duration, material, job_type, tool_no):
    print(f"🎯 Starting simulation thread for {machine_id}")
    thread = Thread(target=generate_sensor_data,
                   args=(machine_id, job_id, duration, material, job_type, tool_no))
    thread.daemon = True
    thread.start()
    print(f"🧵 Thread started for job {job_id}")
    return thread
