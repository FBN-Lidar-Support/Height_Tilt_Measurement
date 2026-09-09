import numpy as np

def apply_sensor_offset(raw_values:list, config):
    corrected = []
    for idx, value in enumerate(raw_values):
        key = f"sensor_{idx+1}"
        corrected.append(float(raw_values[idx]) + float(config["OFFSET_ALL"][key]))
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
def calculate_roll_pitch_relative(n_ref, n_ob):
    # Reference slopes
    a_ref = -n_ref[0] / n_ref[2]
    b_ref = -n_ref[1] / n_ref[2]
    # OB slopes
    a_ob = -n_ob[0] / n_ob[2]
    b_ob = -n_ob[1] / n_ob[2]
    # Relative slopes
    delta_a = a_ob - a_ref
    delta_b = b_ob - b_ref
    # Same orientation convention as existing program
    pitch = np.degrees(np.arctan(delta_b))
    roll = np.degrees(np.arctan(-delta_a))
    return roll, pitch

def Test_OB_Height(measure_axis, spec, sensor_values, product_type, short_reference_diff=1.01):
    """
    Measure points:     S4, S5, S6, S7 = OB measurement points
    LONG RANGE    :     S1, S2, S3 = Reference Plane
    SHORT RANGE   :     S8, S9 = Reference Level
                        S9 is compensated by short_reference_diff
    PASS criteria :     1. S4-S7 ทุกจุดต้องอยู่ใน Spec
                        2. OB Plane Height ต้องอยู่ใน Spec
    Final         :     PASS = All points PASS AND OB Plane PASS
    """
    # ---------------------------------------------------------
    # 1. Spec
    # ---------------------------------------------------------
    nominal = float(spec["nominal"])
    tolerance = float(spec["tolerance"])
    lower_limit = nominal - tolerance
    upper_limit = nominal + tolerance
    product_type = product_type.strip().upper()
    # ---------------------------------------------------------
    # 2. OB Points = S4-S7
    # ---------------------------------------------------------
    test_points = np.array([
        [measure_axis[3][0], measure_axis[3][1], float(sensor_values[3])],
        [measure_axis[4][0], measure_axis[4][1], float(sensor_values[4])],
        [measure_axis[5][0], measure_axis[5][1], float(sensor_values[5])],
        [measure_axis[6][0], measure_axis[6][1], float(sensor_values[6])],
    ], dtype=float)
    # ---------------------------------------------------------
    # 3. Create Reference
    # ---------------------------------------------------------
    if product_type == "LONG RANGE":
        # S1, S2, S3 = Reference Plane
        ref_points = np.array([
            [measure_axis[0][0], measure_axis[0][1], float(sensor_values[0])],
            [measure_axis[1][0], measure_axis[1][1], float(sensor_values[1])],
            [measure_axis[2][0], measure_axis[2][1], float(sensor_values[2])],
        ], dtype=float)
        n_ref, coeffs_ref = fit_plane(ref_points)
        a_ref, b_ref, c_ref = coeffs_ref
        reference_type = "PLANE"
    elif product_type == "SHORT RANGE":
        # S8, S9 = Reference Level
        ref8 = float(sensor_values[7])
        # Mechanical difference from drawing
        ref9 = (float(sensor_values[8]) - float(short_reference_diff))
        z_reference = (ref8 + ref9) / 2.0
        # Treat reference as horizontal plane:
        # z = c
        a_ref = 0.0
        b_ref = 0.0
        c_ref = z_reference
        n_ref = np.array([0.0, 0.0, 1.0])
        reference_type = "LEVEL"
    else:
        raise ValueError(
            f"Invalid product_type: {product_type}. "
            "Use 'LONG RANGE' or 'SHORT RANGE'."
        )
    # ---------------------------------------------------------
    # 4. Check individual S4-S7
    # ---------------------------------------------------------
    point_results = []
    raw_offsets = []
    for i, (x, y, z_actual) in enumerate(test_points):
        # Reference Z at same X/Y position
        z_reference_at_point = (a_ref * x + b_ref * y + c_ref)
        height = float(z_actual - z_reference_at_point)
        raw_offsets.append(height)
        point_pass = (lower_limit <= height <= upper_limit)
        point_results.append({
            "point": f"B{i + 1}",
            "sensor": f"S{i + 4}",
            "actual_z": round(float(z_actual), 3),
            "reference_z": round(float(z_reference_at_point), 3),
            "height": round(height, 3),
            "deviation": round(height - nominal, 3),
            "result": point_pass
        })
    # ---------------------------------------------------------
    # 5. Fit OB Plane from S4-S7
    # ---------------------------------------------------------
    n_ob, coeffs_ob = fit_plane(test_points)
    a_ob, b_ob, c_ob = coeffs_ob
    # ---------------------------------------------------------
    # 6. Calculate OB Plane Height
    #
    # Compare OB Plane and Reference at center X/Y
    # ---------------------------------------------------------
    center_x = float(np.mean(test_points[:, 0]))
    center_y = float(np.mean(test_points[:, 1]))
    z_reference_center = (a_ref * center_x + b_ref * center_y + c_ref)
    z_ob_center = (a_ob * center_x + b_ob * center_y + c_ob)
    ob_plane_height = float(z_ob_center - z_reference_center)
    # ---------------------------------------------------------
    # 7. Check OB Plane
    # ---------------------------------------------------------
    ob_plane_pass = (lower_limit <= ob_plane_height <= upper_limit)
    # ---------------------------------------------------------
    # 8. Plane deviation from nominal
    # ---------------------------------------------------------
    plane_deviation = (ob_plane_height - nominal)
    # ---------------------------------------------------------
    # 9. Final Result
    # ---------------------------------------------------------
    all_point_pass = all(result["result"] for result in point_results)
    final_pass = (all_point_pass and ob_plane_pass)
    # ---------------------------------------------------------
    # 10. Return
    # ---------------------------------------------------------
    return {
        "test": "Test_OB_Height",
        "product_type": product_type,
        "reference_type": reference_type,
        "point_results": point_results,
        "ob_plane_height": round(ob_plane_height, 3),
        "plane_deviation": round(plane_deviation, 3),
        "point_result": ("PASS" if all_point_pass else "FAIL"),
        "plane_result": ("PASS" if ob_plane_pass else "FAIL"),
        "result": ("PASS" if final_pass else "FAIL"),
        "Reference Normal": n_ref,
        "OB Normal": n_ob,
        "limits": {
                "nominal": nominal,
                "tolerance": tolerance,
                "lower": lower_limit,
                "upper": upper_limit
        }
    }

def Test_OB_Tilt(measure_axis, sensor_values, product_type):
    """
    Test_OB_Tilt_Cover
    LONG RANGE:
        Reference Plane = S1, S2, S3
        OB Plane        = S4, S5, S6, S7
        Calculate:
            - Relative tilt angle
            - Roll
            - Pitch
            - Roll direction
            - Pitch direction
        No PASS / FAIL criteria.
    SHORT RANGE:
        S8, S9 only cannot create a 3D reference plane.
        Return N/A.
    """
    # ==================================================
    # SHORT RANGE
    # ==================================================
    if product_type.upper() == "SHORT RANGE":
        return {
            "test":             "Test_OB_Tilt_Cover",
            "range_type":       "SHORT RANGE",
            "Reference Normal": "N/A",
            "OB Normal":        "N/A",
            "tilt_angle":       "N/A",
            "roll":             "N/A",
            "pitch":            "N/A",
            "roll_direction":   "N/A",
            "pitch_direction":  "N/A",
            "result":           "N/A"
        }
    # ==================================================
    # LONG RANGE
    # ==================================================
    elif product_type.upper() == "LONG RANGE":
        # ----------------------------------------------
        # Reference Plane : S1-S3
        # ----------------------------------------------
        ref_points = np.array([
            [measure_axis[0][0], measure_axis[0][1], float(sensor_values[0])],
            [measure_axis[1][0], measure_axis[1][1], float(sensor_values[1])],
            [measure_axis[2][0], measure_axis[2][1], float(sensor_values[2])],
        ], dtype=float)
        # ----------------------------------------------
        # OB Plane : S4-S7
        # ----------------------------------------------
        ob_points = np.array([
            [measure_axis[3][0], measure_axis[3][1], float(sensor_values[3])],
            [measure_axis[4][0], measure_axis[4][1], float(sensor_values[4])],
            [measure_axis[5][0], measure_axis[5][1], float(sensor_values[5])],
            [measure_axis[6][0], measure_axis[6][1], float(sensor_values[6])],
        ], dtype=float)
        # ----------------------------------------------
        # Fit Planes
        # ----------------------------------------------
        n_ref, coeffs_ref = fit_plane(ref_points)
        n_ob, coeffs_ob = fit_plane(ob_points)
        # ----------------------------------------------
        # Relative Tilt Angle
        # ----------------------------------------------
        tilt_angle = calculate_relative_tilt(n_ref, n_ob)
        # ----------------------------------------------
        # Roll / Pitch relative to Reference Plane
        # ----------------------------------------------
        roll, pitch = calculate_roll_pitch_relative(n_ref, n_ob)
        return {
            "test":             "Test_OB_Tilt_Cover",
            "range_type":       "LONG RANGE",
            "Reference Normal": n_ref,
            "OB Normal":        n_ob,
            "tilt_angle":       round(float(tilt_angle), 3),
            "roll":             round(float(roll), 3),
            "pitch":            round(float(pitch), 3),
            "roll_direction":   describe_roll_direction(roll),
            "pitch_direction":  describe_pitch_direction(pitch),
            "result":           "N/A"
        }
    else:
        raise ValueError(
            f"Invalid range_type: {product_type}. "
            "Use 'LONG RANGE' or 'SHORT RANGE'."
        )

def Test_OB_Relative(sensor_value, tolerance: float):
    b1 = float(sensor_value[3])
    b2 = float(sensor_value[4])
    b3 = float(sensor_value[5])
    b4 = float(sensor_value[6])
    
    rear_avg = (b1 + b2) / 2.0
    front_avg = (b3 + b4) / 2.0
    diff = rear_avg - front_avg
    test_pass = abs(diff) < tolerance
    return {
        "test": "Test_OB_Tilt_Relative",
        "rear_AVG": round(rear_avg, 3),
        "front_AVG": round(front_avg, 3),
        "bench_pts": [round(b1, 3), round(b2, 3), round(b3, 3), round(b4, 3)], 
        "deviation": round(diff, 3),
        "limit": float(tolerance),
        "result": "PASS" if test_pass else "FAIL"
    }
# sensor = [-0.3400699999999999, -0.13400000000000034, -0.11902999999999997, -18.47449, -18.087999999999997, -18.57553, -17.24611, -46.603629999999995, -43.07082]
# x = Test_OB_Relative(sensor_value= sensor, tolerance= 0.300)
# print(x)