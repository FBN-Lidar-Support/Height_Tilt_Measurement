from measurement import analyze_displacement
import configparser

if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("C:\Projects\Cells_DR\Properties\Config.ini")
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

    sensor_values = [0.0, 0.0, 0.0, -18.11, -18.11, -18.11, -18.11]
    result = analyze_displacement(mesure_points, spec, sensor_values)
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
    print(f"Result: {result['result']}")
