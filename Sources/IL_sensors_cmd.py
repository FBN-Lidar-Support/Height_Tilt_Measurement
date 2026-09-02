import socket
import time
from concurrent.futures import ThreadPoolExecutor

def Reset_sensor(IP: str, PORT: int, wait=0.1):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            s.connect((IP, PORT))
            for i in range(7):
                sensor_num = i+1
                command = f"SW,0{sensor_num},001,+000000001\r\n"
                s.sendall(command.encode())
                time.sleep(wait)
                print(s.recv(1024).decode().strip())
            return True
    except Exception as e:
        print(f"TCP Error: {e}" )
        return False
    
def Read_all_sensor(IP: str, PORT: int, wait=0.1):
    """
    Read all sensor values from one DL-EN1 / one IP.
    Return raw response string or False.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            s.connect((IP, PORT))
            s.sendall(b"M0\r\n")
            time.sleep(wait)
            response = s.recv(1024).decode().strip()
            return response
    except Exception as e:
        print(f"TCP Error {IP}: {e}")
        return False
    
def parse_sensor_response(response: str):
    """
    Convert raw response string to list of float values in mm.
    Example response may be:
    M0,+00123,+00456,...
    or
    +00123,+00456,...
    Adjust this function if your actual response format is different.
    """
    if response is False or response is None:
        return False
    try:
        values = response.split(",")
        # ถ้าตัวแรกเป็น command/header เช่น M0 ให้ตัดออก
        if not values[0].replace("-", "").replace("+", "").isdigit():
            values.pop(0)
        # Convert sensor raw value to mm
        sensor_values = [int(v) / 1000 for v in values if v != ""]
        return sensor_values
    except Exception as e:
        print(f"Parse Error: {e}")
        print(f"Raw response: {response}")
        return False
    
def Read_all_sensor_dual(IP_OLD: str, PORT_OLD: int, IP_NEW: str, PORT_NEW: int, wait=0.1):
    """
    Read sensors from 2 LAN/IP at the same time.
    OLD IP = Sensor 1-7
    NEW IP = Sensor 8-9
    """
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_old = executor.submit(Read_all_sensor, IP_OLD, PORT_OLD, wait)
        future_new = executor.submit(Read_all_sensor, IP_NEW, PORT_NEW, wait)
        old_response = future_old.result()
        new_response = future_new.result()
    if old_response is False:
        print("Cannot read OLD sensor IP")
        return False
    if new_response is False:
        print("Cannot read NEW sensor IP")
        return False
    old_values = parse_sensor_response(old_response)
    new_values = parse_sensor_response(new_response)
    if old_values is False:
        print("Cannot parse OLD sensor response")
        return False
    if new_values is False:
        print("Cannot parse NEW sensor response")
        return False
    all_values = {}
    for idx, value in enumerate(old_values):
        sensor_name = f"sensor_{idx+1}"
        all_values[sensor_name] = value
    all_values["sensor_8"] = new_values[0]
    all_values["sensor_9"] = new_values[1]
    return all_values

# IP1 = "169.254.148.227"
# IP2 = "169.254.148.228"
# PORT1 = 64000
# PORT2 = 64000

# def Reset_Offset_Sensor(IP: str, PORT: int, wait=0.1):
#     try:
#         with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#             s.settimeout(3)
#             s.connect((IP, PORT))
#             for i in range(7):
#                 sensor_num = i+1
#                 command = f"SW,0{sensor_num},002,+000000001\r\n"
#                 s.sendall(command.encode())
#                 time.sleep(wait)
#                 print(s.recv(1024).decode().strip())
#             return True
#     except Exception as e:
#         print(f"TCP Error: {e}" )
#         return False

# Reset_Offset_Sensor(IP2, PORT2)