from measurement import analyze_displacement
from IL_sensors_cmd import Reset_sensor, Read_all_sensor
import configparser
import numpy as np
from datetime import datetime
import csv
import time 

if __name__ == "__main__":
    start_time = datetime(2025, 11, 4, 19, 0, 0)
    stop_time = datetime(2025, 11, 5, 7, 0, 0)
    
    config = configparser.ConfigParser()
    config.read("C:\Projects\Cells_DR\Properties\Config.ini")
    IL_IP = config["DEFAULT"].get("IL_IP", "")
    IL_PORT = int(config["DEFAULT"].get("IL_PORT", ""))
    spec = {
            "limit": float(config["SPEC"].get("limit", "")),
            "tolerance": float(config["SPEC"].get("tolerance", ""))
            }
    mesure_points = []
    for i in range(1, 4):
        x = float(config["SPEC"].get(f"cover{i}_X"))
        y = float(config["SPEC"].get(f"cover{i}_Y"))
        mesure_points.append([x, y])
    for i in range(1, 5):
        x = float(config["SPEC"].get(f"bench{i}_X"))
        y = float(config["SPEC"].get(f"bench{i}_Y"))
        mesure_points.append([x, y])

    time.sleep(10)
    # Reset_sensor(IL_IP, IL_PORT)
    # quit()
    # print("all sensor reset to default")
    print("Waiting to start....")
    while True:
        if datetime.now() >= start_time:
            print("Start collect results")
            filedate = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            while True:
                IL_status = Read_all_sensor(IL_IP, IL_PORT)
                array_values = IL_status.split(",")
                array_values.pop(0)
                # print(array_values)
                measured_values = np.array(array_values).astype(int) / 1000

                sensor_values = [0.0, 0.0, 0.0, -18.11, -18.11, -18.11, -18.11]
                result = analyze_displacement(mesure_points, spec, measured_values)
                measured_values_str = measured_values.astype(str)
                bench_pts = result["offset_result"]

                for r in result["offset_result"]:
                    print(f"Bench {r['point']}: Actual Z = {r['actual_z']:.3f} mm | "
                        f"z_on_cover = {r['z_on_cover']:.3f} mm | "
                        f"Offset = {r['offset']:.3f} mm | "
                        f"Result = {'PASS' if r['result'] else 'FAIL'}")
                print(f"Tilt angle: {result['tilt_angle']:.4f}°")
                print(f"Pitch: {result['pitch_direction']}")
                print(f"Roll: {result['roll_direction']}")
                print(f"bench plane offset: {result['bench_plane_offset']:.4f} mm")
                print(f"Plane Deviation: {result['plane_deviation']:.3f}")
                print(f"Result: {result['Final_Result']}")
                
                now = datetime.now()

                df = {
                    "EN": "524161",
                    "SN": "CIN252400003",
                    "SN OB": "COB252400002",
                    "Time Stamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "Raw Cover 1": measured_values_str[0],
                    "Raw Cover 2": measured_values_str[1],
                    "Raw Cover 3": measured_values_str[2],
                    "Raw Bench 1": measured_values_str[3],
                    "Raw Bench 2": measured_values_str[4],
                    "Raw Bench 3": measured_values_str[5],
                    "Raw Bench 4": measured_values_str[6],
                    # "Reference Normal": str(result["Reference Normal"]),
                    "Bench offset 1": f"{bench_pts[0]['offset']:.3f}",
                    "Bench offset 2": f"{bench_pts[1]['offset']:.3f}",
                    "Bench offset 3": f"{bench_pts[2]['offset']:.3f}",
                    "Bench offset 4": f"{bench_pts[3]['offset']:.3f}",
                    # "Test Normal": str(result["Test Normal"]),
                    "Tilt angle between planes": f"{result['tilt_angle']:.4f}",
                    "Tilt Pitch direction": f"{result['pitch_direction']}",
                    "Tilt Roll direction":f"{result['roll_direction']}",
                    "OB Tilt Result" : result["OB_tilt_result"],
                    "Bench plane Offset": f"{result['bench_plane_offset']:.3f}",
                    "Deviation": f"{result['plane_deviation']:.3f}",
                    "OB Hight Result" : result["OB_height_result"],
                    "Result": result['Final_Result']
                }
                filepath = f"T:\_A\AtthaphanP\INNOVIZ\Displacement\Longrun_test_Week2_{filedate}.csv"
                with open(filepath, mode='a', encoding="utf-8", newline='') as file:
                    writer = csv.DictWriter(file, fieldnames= df.keys())
                    if file.tell() == 0:
                        writer.writeheader()

                    writer.writerow(df)
                if now >= stop_time:
                    print("Finish collect results")
                    quit()

                print("---------------------------------------------------------------------------------------")
                time.sleep(60)