import numpy as np

def apply_sensor_offset(raw_values, config, product_type):
    corrected = raw_values.copy()
    if product_type == "LONG RANGE":
        section = "OFFSET_LR"
        sensors = [1,2,3,4,5,6,7]
    elif product_type == "SHORT RANGE":
        section = "OFFSET_SR"
        sensors = [4,5,6,7,8,9]
    else:
        raise ValueError("Unknown Model")
    for i in sensors:
        key = f"sensor_{i}"
        corrected[key] = (float(raw_values[key]) + float(config[section][key])
        )
    return corrected

def fit_plane(points):
    X = np.c_[points[:, 0], points[:, 1], np.ones(points.shape[0])]
    Z = points[:, 2]
    coeffs, *_ = np.linalg.lstsq(X, Z, rcond=None)
    a, b, c = coeffs
    normal = np.array([-a, -b, 1.0])
    normal /= np.linalg.norm(normal)
    return normal, coeffs
def calculate_relative_tilt(n_ref, n_test):
    dot = np.dot(n_ref, n_test)
    angle_rad = np.arccos(np.clip(dot, -1.0, 1.0))
    return np.degrees(angle_rad)
def calculate_roll_pitch_from_ref(n_test):
    nx, ny, nz = n_test
    pitch = np.degrees(np.arctan2(ny, nz))
    roll = np.degrees(np.arctan2(-nx, np.sqrt(ny**2 + nz**2)))
    return roll, pitch
def describe_pitch_direction(pitch, threshold=0.001):
    if pitch > threshold:
        return f"Tilt backward {abs(pitch):.3f}°"
    elif pitch < -threshold:
        return f"Tilt forward {abs(pitch):.3f}°"
    else:
        return "No forward/backward tilt"
def describe_roll_direction(roll, threshold=0.001):
    if roll > threshold:
        return f"Tilt left {abs(roll):.3f}°"
    elif roll < -threshold:
        return f"Tilt right {abs(roll):.3f}°"
    else:
        return "No left/right tilt"
    
def analyze_displacement_LR(sensors_pts, spec, sensor_values):
    """
    Return fields:
      - Reference Normal, Test Normal, tilt_angle, roll, pitch
      - offset_result: รายการผลของ bench 1–4 (เทียบ cover plane ที่ตำแหน่งเดียวกัน)
      - bench_plane_offset: ระยะ Z ของ bench plane (ที่จุดกึ่งกลาง XY) เทียบ cover plane (หน่วย mm)
      - plane_deviation: ความต่างจากสเปค = bench_plane_offset - spec['limit']  (หน่วย mm)
      - OB_tilt_test_result: PASS/FAIL (ถ้ามี bench point ใดๆ เกิน limit → FAIL)
      - OB_height_result: PASS/FAIL (ถ้า bench_plane_offset เกิน limit → FAIL)
      - Final_Result: PASS/FAIL (ทั้งสองเงื่อนไขต้องผ่าน)
    """
    # 1) แยก cover (3 จุด) และ bench (4 จุด)
    ref_points = np.array([
        [sensors_pts[0][0], sensors_pts[0][1], sensor_values["sensor_1"]],
        [sensors_pts[1][0], sensors_pts[1][1], sensor_values["sensor_2"]],
        [sensors_pts[2][0], sensors_pts[2][1], sensor_values["sensor_3"]],
    ], dtype=float)
    test_points = np.array([
        [sensors_pts[3][0], sensors_pts[3][1], sensor_values["sensor_4"]],
        [sensors_pts[4][0], sensors_pts[4][1], sensor_values["sensor_5"]],
        [sensors_pts[5][0], sensors_pts[5][1], sensor_values["sensor_6"]],
        [sensors_pts[6][0], sensors_pts[6][1], sensor_values["sensor_7"]],
    ], dtype=float)
    # Spec window
    lower_limit = float(spec["limit"]) - float(spec["tolerance"])
    upper_limit = float(spec["limit"]) + float(spec["tolerance"])
    # 2) Fit cover plane
    n_ref, coeffs_ref = fit_plane(ref_points)
    a_ref, b_ref, c_ref = coeffs_ref
    # 3) คำนวณระยะ Z ของแต่ละ bench point เทียบ cover plane (ตำแหน่งเดียวกัน)
    bench_results = []
    for i, (x, y, z_actual) in enumerate(test_points):
        z_on_cover = a_ref * x + b_ref * y + c_ref
        offset_z = z_actual - z_on_cover
        in_spec = (lower_limit <= offset_z <= upper_limit)
        bench_results.append({
            "point": i + 1,
            "actual_z": float(z_actual),
            "z_on_cover": float(z_on_cover),
            "offset": float(offset_z),          # ระยะจากจุด → cover plane (แนว Z)
            "result": bool(in_spec)
        })
    # 4) Fit bench plane (ค่าจริง)
    n_test, coeffs_test = fit_plane(test_points)
    # 5) Tilt, roll, pitch
    tilt_angle = calculate_relative_tilt(n_ref, n_test)
    roll, pitch = calculate_roll_pitch_from_ref(n_test)
    # 6) Bench plane offset ที่จุดกึ่งกลาง XY (เทียบ cover plane)
    center_x = float(np.mean(test_points[:, 0]))
    center_y = float(np.mean(test_points[:, 1]))
    z_cover_center = a_ref * center_x + b_ref * center_y + c_ref
    z_bench_center = coeffs_test[0] * center_x + coeffs_test[1] * center_y + coeffs_test[2]
    bench_plane_offset = float(z_bench_center - z_cover_center)        # ระยะ Z ของ plane-to-plane ที่จุดกึ่งกลาง
    plane_deviation = float(bench_plane_offset - float(spec["limit"])) # ค่าต่างจาก nominal
    plane_in_spec = (lower_limit <= bench_plane_offset <= upper_limit)
    # 7) สรุปผลย่อย + ผลรวม
    ob_tilt_pass   = all(r["result"] for r in bench_results)    # ถ้าจุดใดจุดหนึ่งเกิน → FAIL
    ob_height_pass = bool(plane_in_spec)                        # ถ้า bench_plane_offset เกิน → FAIL
    final_pass     = ob_tilt_pass and ob_height_pass
    return {
        "Reference Normal": n_ref,
        "Test Normal": n_test,
        "tilt_angle": float(tilt_angle),
        "roll": float(roll),
        "pitch": float(pitch),
        "roll_direction": describe_roll_direction(roll),
        "pitch_direction": describe_pitch_direction(pitch),
        "offset_result": bench_results,                 # รายการผลของ Bench 1–4
        "bench_plane_offset": bench_plane_offset,       # ระยะ Z ของ plane (กึ่งกลาง) เทียบ cover
        "plane_deviation": plane_deviation,             # ต่างจากสเปค (-18.11) กี่ mm (บวก/ลบ)
        "OB_tilt_result":   "PASS" if ob_tilt_pass   else "FAIL",
        "OB_height_result":      "PASS" if ob_height_pass else "FAIL",
        "Final_Result":          "PASS" if final_pass     else "FAIL",
        # เผื่ออยากโชว์กรอบสเปคที่ใช้ตัดสิน
        "limits": {
            "limit": float(spec["limit"]),
            "tolerance": float(spec["tolerance"]),
            "lower": lower_limit,
            "upper": upper_limit
        }
    }
    
def analyze_displacement_SR(sensors_pts, spec, sensor_values):
    """
    SR Model
    Reference:
        Sensor 8
        Sensor 9
    Measure:
        Sensor 4-7
    Height only
    """
    lower_limit = float(spec["limit"]) - float(spec["tolerance"])
    upper_limit = float(spec["limit"]) + float(spec["tolerance"])
    # Reference Sensor
    C1 = float(sensor_values["sensor_8"])
    C2 = float(sensor_values["sensor_9"]) - 1.01
    reference_z = (C1 + C2) / 2
    bench_values = [
        float(sensor_values[3]),  # Bench 1
        float(sensor_values[4]),  # Bench 2
        float(sensor_values[5]),  # Bench 3
        float(sensor_values[6])   # Bench 4
    ]
    offset_result = []
    for i, z_actual in enumerate(bench_values):
        offset_z = z_actual - reference_z
        point_pass = (lower_limit <= offset_z <= upper_limit)
        offset_result.append({
            "point": i + 1,
            "actual_z": z_actual,
            "reference_z": reference_z,
            "offset": offset_z,
            "result": point_pass
        })
    # Height Result
    bench_plane_offset = np.mean([r["offset"] for r in offset_result])
    plane_deviation = (bench_plane_offset - float(spec["limit"]))
    ob_height_pass = (lower_limit <= bench_plane_offset <= upper_limit)
    return {
        "Reference Normal": "N/A",
        "Test Normal": "N/A",
        "tilt_angle": "N/A",
        "roll": "N/A",
        "pitch": "N/A",
        "roll_direction": "N/A",
        "pitch_direction": "N/A",
        "offset_result": offset_result,
        "bench_plane_offset": bench_plane_offset,
        "plane_deviation": plane_deviation,
        "OB_tilt_result": "N/A",
        "OB_height_result":
            "PASS" if ob_height_pass else "FAIL",
        "Final_Result":
            "PASS" if ob_height_pass else "FAIL",
        "limits": {
            "limit": float(spec["limit"]),
            "tolerance": float(spec["tolerance"]),
            "lower": lower_limit,
            "upper": upper_limit
        }
    }