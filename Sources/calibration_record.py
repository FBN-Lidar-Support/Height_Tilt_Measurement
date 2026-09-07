import configparser
from pathlib import Path

def create_calibration_ini(CALIBRATION_FILE: Path):
    # ถ้ามีไฟล์อยู่แล้ว ไม่ต้องสร้างใหม่
    if CALIBRATION_FILE.exists():
        print("calibration.ini already exists")
        return
    # สร้าง folder Properties ถ้ายังไม่มี
    CALIBRATION_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )
    config = configparser.ConfigParser()
    # =========================
    # CALIBRATION INFO
    # =========================
    config["CALIBRATION_INFO"] = {
        "last_calibrate": "",
        "calibrate_master": "",
        "calibrate_by": "",
        "status": "",
        "sample_count": "100"
    }
    
    # =========================
    # SENSOR OFFSET
    # =========================
    config["OFFSET_ALL"] = {
        f"sensor_{i}": ""
        for i in range(1, 10)
    }
    # Write file
    with open(
        CALIBRATION_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        config.write(file)
    print("Created calibration.ini")