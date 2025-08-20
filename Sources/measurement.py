import numpy as np
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
    roll = np.degrees(np.arctan2(ny, nz))
    pitch = np.degrees(np.arctan2(-nx, np.sqrt(ny**2 + nz**2)))
    return roll, pitch
def describe_roll_direction(roll, threshold=0.001):
    if roll > threshold:
        return f"Tilt backward {abs(roll):.3f}°"
    elif roll < -threshold:
        return f"Tilt forward {abs(roll):.3f}°"
    else:
        return "No forward/backward tilt"
def describe_pitch_direction(pitch, threshold=0.001):
    if pitch > threshold:
        return f"Tilt left {abs(pitch):.3f}°"
    elif pitch < -threshold:
        return f"Tilt right {abs(pitch):.3f}°"
    else:
        return "No left/right tilt"
def analyze_displacement(mesure_points, spec, sensor_values):
    # 1. แยก cover (3 จุด) และ bench (4 จุด)
    ref_points = np.array([
        [mesure_points[0][0], mesure_points[0][1], sensor_values[0]],
        [mesure_points[1][0], mesure_points[1][1], sensor_values[1]],
        [mesure_points[2][0], mesure_points[2][1], sensor_values[2]]
    ])
    test_points = np.array([
        [mesure_points[3][0], mesure_points[3][1], sensor_values[3]],
        [mesure_points[4][0], mesure_points[4][1], sensor_values[4]],
        [mesure_points[5][0], mesure_points[5][1], sensor_values[5]],
        [mesure_points[6][0], mesure_points[6][1], sensor_values[6]]
    ])

    lower_limit = spec["limit"] - spec["tolerance"]
    upper_limit = spec["limit"] + spec["tolerance"]
    print(lower_limit, "", upper_limit)

    # 2. Fit cover plane
    n_ref, coeffs_ref = fit_plane(ref_points)
    a_ref, b_ref, c_ref = coeffs_ref
    # 3. คำนวณ offset_z สำหรับแต่ละ bench point
    bench_results = []

    for i, (x, y, z_actual) in enumerate(test_points):
        z_on_cover = a_ref * x + b_ref * y + c_ref
        offset_z = z_actual - z_on_cover
        bench_results.append({
            "point": i + 1,
            "actual_z": z_actual,
            "z_on_cover": z_on_cover,
            "offset": offset_z,
            "result": True if lower_limit <= offset_z <= upper_limit else False
        })
    # 4. Fit bench plane (real z)
    n_test, coeffs_test = fit_plane(test_points)
    # 5. Tilt, roll, pitch
    tilt_angle = calculate_relative_tilt(n_ref, n_test)
    roll, pitch = calculate_roll_pitch_from_ref(n_test)
    # 6. Deviation of plane center (ใช้เป็น plane deviation ที่แท้จริง)
    center_x = np.mean(test_points[:, 0])
    center_y = np.mean(test_points[:, 1])
    z_cover_center = a_ref * center_x + b_ref * center_y + c_ref
    z_bench_center = coeffs_test[0] * center_x + coeffs_test[1] * center_y + coeffs_test[2]
    bench_plane_offset = z_bench_center - z_cover_center
    plane_deviation = bench_plane_offset - spec["limit"]
    plane_deviation_result = True if lower_limit <= bench_plane_offset <= upper_limit else False
    # 7. Final result: ถ้ามีจุดไหน fail หรือ deviation fail → FAIL
    all_pass = all(r["result"] for r in bench_results) and plane_deviation_result
    return {
        "Reference Normal": n_ref,
        "Test Normal": n_test,
        "tilt_angle": tilt_angle,
        "roll": roll,
        "pitch": pitch,
        "roll_direction": describe_roll_direction(roll),
        "pitch_direction": describe_pitch_direction(pitch),
        "bench_plane_offset": bench_plane_offset,
        "plane_deviation": plane_deviation,
        "offset_result": bench_results,
        "result": "PASS" if all_pass else "FAIL"
    }