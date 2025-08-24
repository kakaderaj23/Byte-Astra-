# import pandas as pd
# import matplotlib.pyplot as plt
# import seaborn as sns
# from pymongo import MongoClient
# import os

# def analyze_test_data():
#     client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))
#     db = client["TestLatheDB"]
#     sensory_data = list(db.SensoryData.find())
#     if not sensory_data:
#         print("No test data found!")
#         return

#     df = pd.DataFrame(sensory_data)
#     # Ensure timestamps are datetime
#     if 'timestamp' in df.columns:
#         df['timestamp'] = pd.to_datetime(df['timestamp'])
#     else:
#         print("No 'timestamp' column in data!")
#         return

#     sensor_columns = ['Temperature', 'Vibration', 'RPM', 'Power']

#     plt.figure(figsize=(16, 12))
#     for i, sensor in enumerate(sensor_columns, 1):
#         plt.subplot(2, 2, i)
#         sns.lineplot(data=df, x='timestamp', y=sensor, hue='JobID', legend='full')
#         plt.title(f'{sensor} over Time by JobID')
#         plt.xlabel('Timestamp')
#         plt.ylabel(sensor)
#         plt.xticks(rotation=45)
#         plt.legend(title='JobID', bbox_to_anchor=(1.05, 1), loc='upper left')
#     plt.tight_layout()
#     plt.show()

# if __name__ == "__main__":
#     analyze_test_data()

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pymongo import MongoClient
import os
import numpy as np


def analyze_sensor_data():
    """Analyze sensor data with new parameters from the predictive maintenance system"""
    client = None
    try:
        client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))

        # Check multiple possible database and collection structures
        # Based on the original code structure, try different collection names
        sensory_data = []

        # Try different database/collection combinations
        possible_configs = [
            {"db_name": "TestLatheDB", "collection_name": "SensoryData"},
            {"db_name": "SensorData", "collection_name": "lathe1_sensory_data"},
            {"db_name": "SensorData", "collection_name": "lathe2_sensory_data"},
            {"db_name": "SensorData", "collection_name": "lathe3_sensory_data"}
        ]

        for config in possible_configs:
            try:
                db = client[config["db_name"]]
                collection = db[config["collection_name"]]
                data = list(collection.find())
                if data:
                    sensory_data.extend(data)
                    print(f"Found {len(data)} records in {config['db_name']}.{config['collection_name']}")
            except Exception as e:
                continue

        if not sensory_data:
            print("No sensor data found in any collection!")
            print("Checked databases: TestLatheDB, SensorData")
            print("Checked collections: SensoryData, lathe1_sensory_data, lathe2_sensory_data, lathe3_sensory_data")
            return

        df = pd.DataFrame(sensory_data)
        print(f"Total records loaded: {len(df)}")
        print("Available columns:", list(df.columns))

        # Ensure timestamps are datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        else:
            print("No 'timestamp' column in data!")
            return

        # New sensor parameters (updated from original)
        new_sensor_columns = [
            'airTemperature',      # Air temperature [K] 
            'processTemperature',  # Process temperature [K]
            'rotationalSpeed',     # Rotational speed [rpm]
            'torque',              # Torque [Nm]
            'toolWear'            # Tool wear [min]
        ]

        # Check which columns actually exist in the data
        available_sensors = [col for col in new_sensor_columns if col in df.columns]
        missing_sensors = [col for col in new_sensor_columns if col not in df.columns]

        if missing_sensors:
            print(f"Warning: Missing sensor columns: {missing_sensors}")

        if not available_sensors:
            print("Error: No expected sensor columns found in data!")
            print("Expected columns:", new_sensor_columns)
            return

        print(f"Analyzing sensors: {available_sensors}")

        # Create comprehensive visualizations
        plt.style.use('default')
        fig = plt.figure(figsize=(20, 16))

        # Plot each available sensor parameter
        n_sensors = len(available_sensors)
        n_cols = 2 if n_sensors > 2 else n_sensors
        n_rows = (n_sensors + 1) // 2

        for i, sensor in enumerate(available_sensors, 1):
            plt.subplot(n_rows, n_cols, i)

            # Handle different grouping columns
            group_col = None
            if 'jobId' in df.columns:
                group_col = 'jobId'
            elif 'JobID' in df.columns:
                group_col = 'JobID'
            elif 'machineId' in df.columns:
                group_col = 'machineId'

            if group_col and len(df[group_col].unique()) <= 10:  # Only group if reasonable number of groups
                sns.lineplot(data=df, x='timestamp', y=sensor, hue=group_col, alpha=0.8)
                plt.legend(title=group_col, bbox_to_anchor=(1.05, 1), loc='upper left')
            else:
                plt.plot(df['timestamp'], df[sensor], alpha=0.7, linewidth=1)

            # Add appropriate titles and labels with units
            sensor_labels = {
                'airTemperature': 'Air Temperature [K]',
                'processTemperature': 'Process Temperature [K]',
                'rotationalSpeed': 'Rotational Speed [rpm]',
                'torque': 'Torque [Nm]',
                'toolWear': 'Tool Wear [min]'
            }

            plt.title(f'{sensor_labels.get(sensor, sensor)} over Time', fontsize=12, fontweight='bold')
            plt.xlabel('Timestamp', fontsize=10)
            plt.ylabel(sensor_labels.get(sensor, sensor), fontsize=10)
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

        # Generate summary statistics
        print("\n" + "="*60)
        print("SENSOR DATA SUMMARY STATISTICS")
        print("="*60)

        for sensor in available_sensors:
            sensor_label = {
                'airTemperature': 'Air Temperature [K]',
                'processTemperature': 'Process Temperature [K]',
                'rotationalSpeed': 'Rotational Speed [rpm]',
                'torque': 'Torque [Nm]',
                'toolWear': 'Tool Wear [min]'
            }.get(sensor, sensor)

            print(f"\n{sensor_label}:")
            print(f"  Mean: {df[sensor].mean():.2f}")
            print(f"  Std:  {df[sensor].std():.2f}")
            print(f"  Min:  {df[sensor].min():.2f}")
            print(f"  Max:  {df[sensor].max():.2f}")
            print(f"  Range: {df[sensor].max() - df[sensor].min():.2f}")

        # Correlation analysis
        if len(available_sensors) > 1:
            print("\n" + "="*60)
            print("SENSOR CORRELATION ANALYSIS")
            print("="*60)

            correlation_matrix = df[available_sensors].corr()
            print(correlation_matrix.round(3))

            # Plot correlation heatmap
            plt.figure(figsize=(10, 8))
            sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0,
                       square=True, fmt='.3f', cbar_kws={'label': 'Correlation Coefficient'})
            plt.title('Sensor Parameter Correlation Matrix', fontsize=14, fontweight='bold')
            plt.tight_layout()
            plt.show()

        # Time-based analysis if data spans reasonable time
        time_span = df['timestamp'].max() - df['timestamp'].min()
        if time_span.total_seconds() > 300:  # More than 5 minutes of data
            print("\n" + "="*60)
            print("TIME-BASED ANALYSIS")
            print("="*60)
            print(f"Data time span: {time_span}")
            print(f"Total data points: {len(df)}")
            print(f"Average sampling interval: {time_span.total_seconds() / len(df):.1f} seconds")

            # Detect trends for key parameters
            for sensor in available_sensors:
                if sensor in ['processTemperature', 'toolWear', 'torque']:
                    # Calculate trend using linear regression
                    x = np.arange(len(df))
                    y = df[sensor].values
                    trend_coef = np.polyfit(x, np.asarray(y, dtype=float), 1)[0]

                    trend_direction = "increasing" if trend_coef > 0 else "decreasing"
                    sensor_label = {
                        'processTemperature': 'Process Temperature',
                        'toolWear': 'Tool Wear', 
                        'torque': 'Torque'
                    }.get(sensor, sensor)

                    print(f"{sensor_label} trend: {trend_direction} ({trend_coef:.4f}/sample)")

    except Exception as e:
        print(f"Error analyzing sensor data: {str(e)}")
        import traceback
    finally:
        if client is not None:
            client.close()

def analyze_legacy_data():
    """Analyze data with original parameter names for backward compatibility"""
    client = None
    try:
        client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))
        client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))
        db = client["TestLatheDB"]
        sensory_data = list(db.SensoryData.find())

        if not sensory_data:
            print("No legacy test data found!")
            return

        df = pd.DataFrame(sensory_data)

        # Ensure timestamps are datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        else:
            print("No 'timestamp' column in legacy data!")
            return

        # Original sensor parameters
        legacy_sensor_columns = ['Temperature', 'Vibration', 'RPM', 'Power']
        available_legacy = [col for col in legacy_sensor_columns if col in df.columns]

        if not available_legacy:
            print("No legacy sensor columns found!")
            return

        print(f"Analyzing legacy sensors: {available_legacy}")

        plt.figure(figsize=(16, 12))
        for i, sensor in enumerate(available_legacy, 1):
            plt.subplot(2, 2, i)

            group_col = 'JobID' if 'JobID' in df.columns else None
            if group_col:
                sns.lineplot(data=df, x='timestamp', y=sensor, hue=group_col, legend='full')
                plt.legend(title='JobID', bbox_to_anchor=(1.05, 1), loc='upper left')
            else:
                plt.plot(df['timestamp'], df[sensor])

            plt.title(f'{sensor} over Time', fontweight='bold')
            plt.xlabel('Timestamp')
            plt.ylabel(sensor)
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    except Exception as e:
        print(f"Error analyzing legacy data: {str(e)}")
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    print("Starting sensor data analysis...")
    print("Attempting to analyze data with new parameters first...")
    analyze_sensor_data()

    print("\n" + "="*60)
    print("Checking for legacy data format...")
    analyze_legacy_data()
