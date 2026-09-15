from pathlib import Path
import shutil, random
from openpyxl import load_workbook, Workbook
import csv
import configparser
from IL_sensors_cmd import Read_all_sensor_dual
from measurement import Test_OB_Height, Test_OB_Relative, apply_sensor_offset

config = configparser.ConfigParser()
config.read(r"C:\Projects\Cells_DR\Properties\Config.ini")
cal = configparser.ConfigParser()
cal.read(r"C:\Projects\Cells_DR\Properties\Calibration.ini")
# Sensor XY
measure_axis = []
for i in range(1, 10):
    x, y = config["SENSOR_POSITION"][f"sensor_{i}"].split(",")
    measure_axis.append([float(x), float(y)])
# ลอง LR ก่อน
spec = {
    "nominal": config.getfloat("Test_OB_Hight", "LR_nominal"),
    "tolerance": config.getfloat("Test_OB_Hight", "LR_tolerance")
}
relative_limit = config.getfloat("Test_OB_Relative", "LR_tolerance")

COLS = [
    "B1_Height","B2_Height","B3_Height","B4_Height",
    "OB_Plane_Height","Rear_Avg","Front_Avg","Relative_Delta"
]

template = Path(input("GRR template path: ").strip('"'))
output = template.with_name(template.stem + "_Result.xlsx")
if template.suffix.lower() == ".csv":
    wb = Workbook()
    ws = wb.active
    with open(template, "r", newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            ws.append(row)
    wb.save(output)
elif template.suffix.lower() == ".xlsx":
    wb = load_workbook(template)
    ws = wb.active
    wb.save(output)
else:
    raise ValueError("Template must be .csv or .xlsx")
# Remove old Measurement column
if str(ws["D1"].value).strip() == "Measurement":
    ws.delete_cols(4)
# Create output columns
for i, name in enumerate(COLS, 4):
    ws.cell(1, i).value = name
wb.save(output)

for row in range(2, ws.max_row + 1):
    
    run = ws.cell(row, 1).value
    operator = ws.cell(row, 2).value
    part = ws.cell(row, 3).value
    
    if run is None:
        continue
    # Skip completed row
    if ws.cell(row, 4).value is not None:
        continue
    
    print(f"\nRun {run}")
    print(f"Operator : {operator}")
    print(f"Part     : {part}")
    
    cmd = input("Load part and press ENTER [Q=Quit]: ")
    
    if cmd.upper() == "Q":
        break
    
    # ===== MOCK SENSOR VALUES =====
    IP1 = "169.254.148.227"
    IP2 = "169.254.148.228"
    PORT1 = 64000
    PORT2 = 64000
    list_sensors = [0,1,2,3,4,5,6]
    nominal = spec["nominal"]
    raw_values = Read_all_sensor_dual(IP1, PORT1, IP2, PORT2)
    if raw_value is False:
        print("Can not read sensor\nPlease check IL-Sensor power")
        quit()

    raw_value = list(raw_value.values())
    if any(abs(float(value)) > 999 for value in [raw_value[i] for i in list_sensors]):
        print("Sensor out limit:\t", "Please check Sensor or Unit that place in fixture")
        quit()
        
    sensor_values = apply_sensor_offset(raw_values, cal)
    print("\nSensor Values")
    for i, (raw, corrected) in enumerate(
        zip(raw_values, sensor_values),
        start=1
    ):
        print(
            f"S{i}: "
            f"Raw={float(raw):.3f}  "
            f"Corrected={float(corrected):.3f}"
        )
        
    height_result = Test_OB_Height(measure_axis=measure_axis, spec=spec, sensor_values=sensor_values, product_type="LONG RANGE")
    relative_result = Test_OB_Relative(sensor_values, relative_limit)
    
    data = [
        height_result["point_results"][0]["height"],   # B1
        height_result["point_results"][1]["height"],   # B2
        height_result["point_results"][2]["height"],   # B3
        height_result["point_results"][3]["height"],   # B4
        height_result["ob_plane_height"],
        relative_result["rear_AVG"],
        relative_result["front_AVG"],
        relative_result["deviation"]
    ]
    
    for col, value in enumerate(data, 4):
        ws.cell(row, col).value = round(float(value), 3)
    wb.save(output)
    print("Saved")