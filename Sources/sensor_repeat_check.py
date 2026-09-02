from datetime import datetime, timedelta
from pathlib import Path
import json
import sys
import csv
import os
import time
import configparser

from IL_sensors_cmd import Read_all_sensor_dual
from measurement import apply_sensor_offset, analyze_displacement_LR, analyze_displacement_SR
from fitsdll import fn_Handshake, fn_Log, fn_Query

BASE_DIR =  os.path.dirname(Path(__file__).resolve().parent)

config = configparser.ConfigParser()
config_path = os.path.join(BASE_DIR, "Properties", "Config.ini")
try:
    config.read(config_path)
    IP_1 = config["DEFAULT"].get("IP_1", "")
    PORT_1 = int(config["DEFAULT"].get("PORT_1", ""))
    IP_2 = config["DEFAULT"].get("IP_2", "")
    PORT_2 = int(config["DEFAULT"].get("PORT_2", ""))
    LogPath = config["DEFAULT"].get("LogPath", "")
    retry = config["DEFAULT"].get("retry", "")
    type_SR = config["FITs"].get("SR", "").split(",")
    type_LR = config["FITs"].get("LR", "").split(",")
    model = config["FITs"].get("model", "")
    operation = config["FITs"].get("operationlist", "")
    spec_LR = {
    "limit": float(config[f"SPEC-LR"].get("limit", "")),
    "tolerance": float(config[f"SPEC-LR"].get("tolerance", ""))
    }
    spec_SR = {
    "limit": float(config[f"SPEC-SR"].get("limit", "")),
    "tolerance": float(config[f"SPEC-SR"].get("tolerance", ""))
    }
except Exception as e:
    print(f"{e}\nPlease check config.ini")
    print("Close Program", f"{e}\nPlease check config.ini")
    quit()
    
cal = configparser.ConfigParser()
cal_path = os.path.join(BASE_DIR, "Properties", "Calibration.ini")
offset_ALL = {}
try:
    cal.read(cal_path)
    for key, value in cal._sections["OFFSET_ALL"].items():
        offset_ALL[key] = value
except Exception as e:
    print(f"{e}\nPlease check config.ini")
    print("Close Program", f"{e}\nPlease check config.ini")
    quit()

mesure_points = []
for key, value in config._sections["SENSOR_POSITION"].items():
    mesure_points.append(value.split(","))
list_sensors = []
for v in config[f"SPEC-LR"].get("list_sensors", "").split(","):
    list_sensors.append(int(v)-1)

now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filepath = os.path.join(r"C:\Projects\Cells_DR\Logs", f"repeatability_report_{now}.csv")
file_exists = os.path.isfile(filepath)
with open(filepath, "a", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    if not file_exists:
        writer.writerow([
            "timeStamp",
            "Cover1",
            "Cover2",
            "Cover3",
            "Bench1",
            "Bench2",
            "Bench3",
            "Bench4"
        ])

    for i in range(30):
        # input(f"PLEASE  RELOAD UNIT COUNT: {i+1}")
        # time.sleep(0.5)
        raw_value = Read_all_sensor_dual(IP_1, PORT_1, IP_2, PORT_2)
        if raw_value is False:
            print("Can not read sensor\nPlease check IL-Sensor power")
            quit()

        raw_value = list(raw_value.values())
        if any(abs(float(value)) > 999 for value in [raw_value[i] for i in list_sensors]):
            continue

        ##############################################################################        
        measured_values = apply_sensor_offset(raw_value, cal)
        # print(measured_values)
        ##############################################################################
        measured_values_str = [f"{x:.3f}" for x in measured_values][:-2] # Sensors 1-7
        print("="*50)
        print(measured_values_str)
        print("="*50)

        writer.writerow([
            datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f")[:-3],
            *measured_values_str
        ])

        file.flush()
        time.sleep(0.5)