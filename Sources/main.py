from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QInputDialog, QMessageBox, QLineEdit
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPixmap
from PyQt6 import uic
from datetime import datetime
from pathlib import Path
import numpy as np
import sys
import csv
import os
import configparser

from IL_sensors_cmd import Read_all_sensor, Reset_sensor
from measurement import analyze_displacement
from fitsdll import fn_Handshake, fn_Log, fn_Query

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        if getattr(sys, 'frozen', False):
            print("EXE")
            self.BASE_DIR =  Path(sys._MEIPASS)
        else:
            print("Python")
            self.BASE_DIR =  os.path.dirname(Path(__file__).resolve().parent)
        
        uic.loadUi(os.path.join(self.BASE_DIR, "Sources", "GUI", "Displacement_window.ui"), self)
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-software-rasterizer"
        self.exit_confirm_enabled = True
        self.config = configparser.ConfigParser()
        pcname = os.environ['COMPUTERNAME']
        print(pcname)
        self.mesure_points = []

        self.MC = pcname
        try:
            self.config.read(os.path.join(self.BASE_DIR, "Properties", "Config.ini"))
            self.IL_IP = self.config["DEFAULT"].get("IL_IP", "")
            self.IL_PORT = int(self.config["DEFAULT"].get("IL_PORT", ""))
            self.LogPath = self.config["DEFAULT"].get("LogPath", "")
            self.mode = self.config["DEFAULT"].get("prom_mode", "").upper()
            self.retry = self.config["DEFAULT"].get("retry", "")
            self.type_SR = self.config["FITs"].get("SR", "").split(",")
            self.type_LR = self.config["FITs"].get("LR", "").split(",")
            self.model = self.config["FITs"].get("model", "")
            self.operationlist = self.config["FITs"].get("operationlist", "").split(",")
            self.spec = {
                "limit": float(self.config["SPEC"].get("limit", "")),
                "tolerance": float(self.config["SPEC"].get("tolerance", ""))
            }
            for i in range(1, 4):
                x = float(self.config["SPEC"].get(f"cover{i}_X"))
                y = float(self.config["SPEC"].get(f"cover{i}_Y"))
                self.mesure_points.append([x, y])
            for i in range(1, 5):
                x = float(self.config["SPEC"].get(f"bench{i}_X"))
                y = float(self.config["SPEC"].get(f"bench{i}_Y"))
                self.mesure_points.append([x, y])
            # print(self.mesure_points)

        except Exception as e:
            print(f"{e}\nPlease check config.ini")
            print("Close Program", f"{e}\nPlease check config.ini")
            quit()
        
        os.makedirs(self.LogPath, exist_ok=True)
        self.clear_log()

        self.Limit.setText(str(self.spec["limit"]))
        self.tolerance.setText(str(self.spec["tolerance"]))

        self.MainstackedWidget.setCurrentIndex(0)
        self.enLineEdit.setFocus()
        self.enLineEdit.returnPressed.connect(self.LoginButton.click)

        pixmap_insert = QPixmap(os.path.join(self.BASE_DIR, "Properties", "insert_img.jpg"))
        self.insert_img.setPixmap(pixmap_insert)
        # self.insert_img.setScaledContents(True)
        pixmap_remove = QPixmap(os.path.join(self.BASE_DIR, "Properties", "remove_img.jpg"))
        self.remove_img.setPixmap(pixmap_remove)
        # self.remove_img.setScaledContents(True)

        self.timer = QTimer(self)
        self.timer.setInterval(500)

        self.readButton.clicked.connect(self.start_read_loop)
        self.stopButton.clicked.connect(self.stop_read_loop)
        self.timer.timeout.connect(self.read_sensor_data)
        self.setButton.clicked.connect(self.setoffset)

        # action Button 
        self.LoginButton.clicked.connect(self.login)
        self.ModeButton.clicked.connect(self.select_mode)
        self.StartButton.clicked.connect(self.check_serials)
        self.LogoutButton.clicked.connect(self.logout)
        self.FinishButton.clicked.connect(self.finish_cycle)
        self.buttonBox.rejected.connect(self.back_to_main)
        self.buttonBox.accepted.connect(self.save_setting)
        self.ExitButton.clicked.connect(QApplication.quit)

        self.uploadButton.clicked.connect(self.record_results)
        self.retryButton.clicked.connect(self.mainprocess)

    def closeEvent(self, event):
        print("CloseEvent")
        if self.MainstackedWidget.currentIndex() != 0:
            QMessageBox.information(self, "Exit Denied", "You can exit the program at the login screen.")
            event.ignore()
        else:
            event.accept()

    def clear_log(self):
        self.df = {}
        self.sn_cover = ""
        self.sn_bench = ""
        self.product_type = ""
        self.enLineEdit.setText("")
        self.SNCoverValue.setText("")
        self.SNBenchValue.setText("")
        self.lineEdit_Operator.setText("")
        self.lineEdit_Operation.setText("")
        self.lineEdit_Station.setText("")
        self.lineEdit_Serial.setText("")
        self.lineEdit_Serial_2.setText("")
        self.lineEdit_Type.setText("")
        self.Cover_1_Value.setText("")
        self.Cover_2_Value.setText("")
        self.Cover_3_Value.setText("")
        self.Result_tilt_planes.setText("")
        self.Result_Pitch.setText("")
        self.Result_Roll.setText("")
        self.Result_offset.setText("")
        self.Result_offset.setText("")
        self.Result_Deviation.setText("")
        self.Result_offset.setStyleSheet("")
        self.Result_Deviation.setStyleSheet("")
        self.Result_Final.setText("")
        self.Result_Final.setStyleSheet("")

        for i in range(1, 5):
            bench_label = getattr(self, f"Bench_{i}_Value")
            bench_label.setStyleSheet("")
            bench_label.setText("")
            bench_diff = getattr(self, f"diff_Bench_{i}")
            bench_diff.setStyleSheet("")
            bench_diff.setText("")
    
    def select_mode(self):
        password, ok = QInputDialog.getText(self, "Admin login", "Enter admin password:", QLineEdit.EchoMode.Password)
        if ok and password == "Admin123":
            self.MainstackedWidget.setCurrentIndex(4)
            self.setting_window()
        else:
            QMessageBox.warning(self, "Asscess Denied", "Incorrect password.")

    def setting_window(self):
        if self.mode == "ENGINEER":
            self.prom_mode.setCurrentText("ENGINEER")
        else:
            self.prom_mode.setCurrentText("PRODUCTION")

        if self.retry == "True":
            self.tries.setCurrentText("True")
        else:
            self.tries.setCurrentText("False")

        self.Log_Path.setText(self.LogPath)
        self.mean.setText(str(self.spec["limit"]))
        self.tolrance.setText(str(self.spec["tolerance"]))
        self.ip.setText(self.IL_IP)
        self.port.setText(str(self.IL_PORT))
        self.cover_1_X.setText(str(self.mesure_points[0][0]))
        self.cover_2_X.setText(str(self.mesure_points[1][0]))
        self.cover_3_X.setText(str(self.mesure_points[2][0]))
        self.Bench_1_X.setText(str(self.mesure_points[3][0]))
        self.Bench_2_X.setText(str(self.mesure_points[4][0]))
        self.Bench_3_X.setText(str(self.mesure_points[5][0]))
        self.Bench_4_X.setText(str(self.mesure_points[6][0]))
        self.cover_1_Y.setText(str(self.mesure_points[0][1]))
        self.cover_2_Y.setText(str(self.mesure_points[1][1]))
        self.cover_3_Y.setText(str(self.mesure_points[2][1]))
        self.Bench_1_Y.setText(str(self.mesure_points[3][1]))
        self.Bench_2_Y.setText(str(self.mesure_points[4][1]))
        self.Bench_3_Y.setText(str(self.mesure_points[5][1]))
        self.Bench_4_Y.setText(str(self.mesure_points[6][1]))

    def back_to_main(self):
        self.MainstackedWidget.setCurrentIndex(0)

    def save_setting(self):
        self.config.set("DEFAULT", "LogPath", self.Log_Path.text())
        self.config.set("DEFAULT", "prom_mode", self.prom_mode.currentText())
        self.config.set("DEFAULT", "IL_IP", self.ip.text())
        self.config.set("DEFAULT", "IL_PORT", self.port.text())
        self.config.set("DEFAULT", "retry", self.tries.currentText())
        self.config.set("SPEC", "limit", self.mean.text())
        self.config.set("SPEC", "tolerance", self.tolrance.text())
        self.config.set("SPEC", "cover1_x", self.cover_1_X.text())
        self.config.set("SPEC", "cover2_x", self.cover_2_X.text())
        self.config.set("SPEC", "cover3_x", self.cover_3_X.text())
        self.config.set("SPEC", "Bench1_x", self.Bench_1_X.text())
        self.config.set("SPEC", "Bench2_x", self.Bench_2_X.text())
        self.config.set("SPEC", "Bench3_x", self.Bench_3_X.text())
        self.config.set("SPEC", "Bench4_x", self.Bench_4_X.text())
        self.config.set("SPEC", "cover1_y", self.cover_1_Y.text())
        self.config.set("SPEC", "cover2_y", self.cover_2_Y.text())
        self.config.set("SPEC", "cover3_y", self.cover_3_Y.text())
        self.config.set("SPEC", "bench1_y", self.Bench_1_Y.text())
        self.config.set("SPEC", "bench2_y", self.Bench_2_Y.text())
        self.config.set("SPEC", "bench3_y", self.Bench_3_Y.text())
        self.config.set("SPEC", "bench4_y", self.Bench_4_Y.text())

        with open(os.path.join(self.BASE_DIR, "Properties", "Config.ini"), "w") as configfile:
            self.config.write(configfile)
        
        self.reload_config()

    def reload_config(self):
        self.config.read(os.path.join(self.BASE_DIR, "Properties", "Config.ini"))
        try:
            self.config.read(os.path.join(self.BASE_DIR, "Properties", "Config.ini"))
            self.IL_IP = self.config["DEFAULT"].get("IL_IP", "")
            self.IL_PORT = int(self.config["DEFAULT"].get("IL_PORT", ""))
            self.LogPath = self.config["DEFAULT"].get("LogPath", "")
            self.mode = self.config["DEFAULT"].get("prom_mode", "")
            self.retry = self.config["DEFAULT"].get("retry", "")

            self.model = self.config["FITs"].get("model", "")
            self.operationlist = self.config["FITs"].get("operationlist", "").split(",")
            self.spec = {
                "limit": float(self.config["SPEC"].get("limit", "")),
                "tolerance": float(self.config["SPEC"].get("tolerance", ""))
            }
            for i in range(1, 4):
                x = float(self.config["SPEC"].get(f"cover{i}_X"))
                y = float(self.config["SPEC"].get(f"cover{i}_Y"))
                self.mesure_points.append([x, y])
            for i in range(1, 5):
                x = float(self.config["SPEC"].get(f"bench{i}_X"))
                y = float(self.config["SPEC"].get(f"bench{i}_Y"))
                self.mesure_points.append([x, y])

        except Exception as e:
            print(f"{e}\nPlease check config.ini")
            print("Close Program", f"{e}\nPlease check config.ini")
            quit()
    
    def start_read_loop(self):
        self.timer.start()

    def stop_read_loop(self):
        self.timer.stop()

    def read_sensor_data(self):
        IL_raw = Read_all_sensor(self.IL_IP, self.IL_PORT)
        if IL_raw is False:
            print("Can not read sensor\nPlease check IL-Sensor power")
            QMessageBox.critical(self, "IL Sensor ERROR", "Can not read sensor\nPlease check IL-Sensor power")
            quit()

        array_values = IL_raw.split(",")
        array_values.pop(0)
        # print(array_values)
        measured_values = np.array(array_values).astype(int) / 1000
        measured_values_str = measured_values.astype(str)

        self.Curr_Cover_1.setText(measured_values_str[0])
        self.Curr_Cover_2.setText(measured_values_str[1])
        self.Curr_Cover_3.setText(measured_values_str[2])

        self.Curr_Bench_1.setText(measured_values_str[3])
        self.Curr_Bench_2.setText(measured_values_str[4])
        self.Curr_Bench_3.setText(measured_values_str[5])
        self.Curr_Bench_4.setText(measured_values_str[6])

    def setoffset(self):
        print("---------- Function Reset offset sensors ----------")
        Reset_sensor(self.IL_IP, self.IL_PORT)
        print("---------------------- Done -----------------------")
        return

    def login(self):
        self.en = self.enLineEdit.text()
        if len(self.en) == 6:
            self.label_Error_login.setText("")
            QTimer.singleShot(100, self.serial_page)
        else:
            self.label_Error_login.setStyleSheet("color: red;")
            self.label_Error_login.setText("Invalid Employee number")
            return
        
    def logout(self):
        self.MainstackedWidget.setCurrentIndex(0)
        self.clear_log()
            
    def serial_page(self):
        self.MainstackedWidget.setCurrentIndex(1)
        self.SNCoverValue.setFocus()
        self.SNCoverValue.returnPressed.connect(lambda: self.SNBenchValue.setFocus())
        # self.SNBenchValue.returnPressed.connect(self.StartButton.click)

    def settestimg(self):
        if self.product_type == "LONG RANGE":
            imgmodel = "LR_OB.jpg"
        elif self.product_type == "SHORT RANGE":
            imgmodel = "SR_OB.jpg"  
        else:
            return
        pixmap_testpoint = QPixmap(os.path.join(self.BASE_DIR, "Properties", imgmodel))
        self.Testing_point_img.setPixmap(pixmap_testpoint)      

    def check_serials(self):
        print("---------- check_serials ----------")
        self.sn_cover = self.SNCoverValue.text()
        self.sn_bench = self.SNBenchValue.text()
        if self.sn_cover.startswith("TEST"):
            self.mode = "ENGINEER"

        if self.mode == ("ENGINEER"):
            print("Program mode:\t", self.mode)
            self.Mode_text.setText(self.mode)
            if self.sn_cover.startswith("TESTCIN360SR"):
                self.product_type = "SHORT RANGE"
            elif self.sn_cover.startswith("TESTCIN360LR"):
                self.product_type = "LONG RANGE"
            else:
                self.product_type = "LONG RANGE"
            self.lineEdit_Type.setText(self.product_type)
            self.settestimg()
            self.Errorlabel.setText("")
            QTimer.singleShot(100, self.mainprocess)
        else:
            print("Program mode:\t", self.mode)
            self.Mode_text.setText(self.mode)
            PN = fn_Query("Main line", "IN010", self.sn_cover, "Part_Number")
            print(PN)
            if PN in self.type_LR:
                self.product_type = "LONG RANGE"
                self.lineEdit_Type.setText(self.product_type)
                self.settestimg()
            elif PN in self.type_SR:
                self.product_type = "SHORT RANGE"
                self.lineEdit_Type.setText(self.product_type)
                self.settestimg()
            else:
                QMessageBox.critical(self, "Invalid part number", "Unknow Part number please contact Engineer to add new part number to config file.")

            if len(self.sn_cover) == 12 and len(self.sn_bench) == 12:
                for operation_choiced in self.operationlist:
                    fits_status = fn_Handshake(self.model, operation_choiced, self.sn_cover)
                    if fits_status == True:
                        self.Errorlabel.setText("")
                        self.operation = operation_choiced
                        QTimer.singleShot(100, self.mainprocess)
                        break
                else: 
                    self.Errorlabel.setStyleSheet("color: red;")
                    self.Errorlabel.setText(fits_status)
                    self.SNCoverValue.setText("")
                    self.SNBenchValue.setText("")
                    self.SNCoverValue.setFocus()

            else:
                self.Errorlabel.setStyleSheet("color: red;")
                self.Errorlabel.setText("Both SN must be 12 digit")
                self.SNCoverValue.setText("")
                self.SNBenchValue.setText("")
                self.SNCoverValue.setFocus()

    def mainprocess(self):
        print("---------- mainprocess ----------")
        if self.retry == "True":
            self.retryButton.show()
        else:
            self.retryButton.hide()
        for i in range(1, 5):
            bench_label = getattr(self, f"Bench_{i}_Value")
            bench_label.setStyleSheet("")
            bench_label.setText("")
            bench_diff = getattr(self, f"diff_Bench_{i}")
            bench_diff.setStyleSheet("")
            bench_diff.setText("")
            
        self.MainstackedWidget.setCurrentIndex(2)
        self.lineEdit_Operator.setText(self.en)
        self.lineEdit_Operation.setText(self.operation)
        self.lineEdit_Station.setText(self.MC)
        self.lineEdit_Serial.setText(self.sn_cover)
        self.lineEdit_Serial_2.setText(self.sn_bench)

        IL_status = Read_all_sensor(self.IL_IP, self.IL_PORT)
        if IL_status is False:
            print("Can not read sensor\nPlease check IL-Sensor power")
            QMessageBox.critical(self, "IL Sensor ERROR", "Can not read sensor\nPlease check IL-Sensor power")
            quit()

        array_values = IL_status.split(",")
        array_values.pop(0)
        # print(array_values)
        measured_values = np.array(array_values).astype(int) / 1000
        if np.any((measured_values > 999) | (measured_values < -999)):
            QMessageBox.warning(self, "Sensor out limit", "Please check Sensor or Unit that place in fixture")
            self.MainstackedWidget.setCurrentIndex(1)
            self.SNCoverValue.setFocus()
            return
        if self.product_type == "SHORT RANGE":
            measured_values[2] += 2
            
        result = analyze_displacement(self.mesure_points, self.spec, measured_values)
        
        measured_values_str = [f"{v:.3f}" for v in measured_values]
        self.Cover_1_Value.setText(measured_values_str[0])
        self.Cover_2_Value.setText(measured_values_str[1])
        self.Cover_3_Value.setText(measured_values_str[2])

        bench_pts = result["offset_result"]
        for r in result["offset_result"]:
            print(f"Bench {r['point']}: Actual Z = {r['actual_z']:.3f} mm | "
                f"z_on_cover = {r['z_on_cover']:.3f} mm | "
                f"Offset = {r['offset']:.3f} mm | "
                f"Result = {'PASS' if r['result'] else 'FAIL'}")
            bench_label = getattr(self, f"Bench_{r['point']}_Value")
            bench_diff = getattr(self, f"diff_Bench_{r['point']}")
            diff_bench = r['offset'] - self.spec["limit"]
            if r['result']:
                bench_label.setText(f"{r['offset']:.3f}")
                bench_diff.setText(f"{diff_bench:.3f}")
            else:
                bench_label.setStyleSheet("background-color: red; color: white;")
                bench_label.setText(f"{r['offset']:.3f}")
                bench_diff.setStyleSheet("background-color: red; color: white;")
                bench_diff.setText(f"{diff_bench:.3f}")


        print(f"Tilt angle: {result['tilt_angle']:.4f}°")
        print(f"Pitch: {result['pitch_direction']}")
        print(f"Roll: {result['roll_direction']}")
        print(f"bench plane offset: {result['bench_plane_offset']:.4f} mm")
        print(f"Plane Deviation: {result['plane_deviation']:.3f}")
        print(f"Result: {result['Final_Result']}")
        
        self.Result_tilt_planes.setText(f"{result['tilt_angle']:.4f}")
        self.Result_Pitch.setText(f"{result['pitch_direction']}")
        self.Result_Roll.setText(f"{result['roll_direction']}")
        self.Result_offset.setText(f"{result['bench_plane_offset']:.3f}")
        self.Result_Deviation.setText(f"{result['plane_deviation']:.3f}")

        if result["OB_tilt_result"] == "PASS":
            self.Result_tilt.setStyleSheet("background-color: green; color: white; font-weight: bold;")
            self.Result_tilt.setText(result["OB_tilt_result"])
        else:
            self.Result_tilt.setStyleSheet("background-color: red; color: white; font-weight: bold;")
            self.Result_tilt.setText(result["OB_tilt_result"])

        if result["OB_height_result"] == "PASS":
            self.Result_hight.setStyleSheet("background-color: green; color: white; font-weight: bold;")
            self.Result_hight.setText(result["OB_height_result"])
            self.Result_offset.setStyleSheet("")
            self.Result_Deviation.setStyleSheet("")
        else:
            self.Result_hight.setStyleSheet("background-color: red; color: white; font-weight: bold;")
            self.Result_hight.setText(result["OB_height_result"])
            self.Result_offset.setStyleSheet("background-color: red; color: white; font-weight: bold;")
            self.Result_Deviation.setStyleSheet("background-color: red; color: white; font-weight: bold;")
          
        if result['Final_Result'] == "PASS":
            self.Result_Final.setStyleSheet("background-color: green; color: white; font-weight: bold;")
            self.Result_Final.setText(result['Final_Result'])
        else:
            self.Result_Final.setStyleSheet("background-color: red; color: white; font-weight: bold;")
            self.Result_Final.setText(result['Final_Result'])
        
        self.df = {
            "EN": self.en,
            "SN": self.sn_cover,
            "SN OB": self.sn_bench,
            "Time Stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
        # print(self.df)

    def record_results(self):
        if self.mode == "ENGINEER":
            now = datetime.now().strftime("%Y-%m-%d")
            filepath = os.path.join(self.LogPath, "ENGINEER_Log", f"{self.sn_cover}_{now}.csv")
            write_header = not os.path.exists(filepath)
            with open(filepath, mode='a', encoding="utf-8", newline='') as file:
                writer = csv.DictWriter(file, fieldnames=self.df.keys())
                if write_header:
                    writer.writeheader()
                writer.writerow(self.df)
        else:
            now = self.df["Time Stamp"].replace(":","-")
            filepath = os.path.join(self.LogPath, f"{self.sn_cover}_{now}.csv")
            with open(filepath, mode='w', encoding="utf-8", newline='') as file:
                writer = csv.writer(file)
                writer.writerow(self.df.keys())  # Write header
                writer.writerow(self.df.values())  # Write values
        
        if self.df["Result"] == "FAIL":
            self.df["Defect code"] = "IN375-001"

        parameters = ";".join(self.df.keys())
        values = ";".join(self.df.values())
        
        if self.mode == "PRODUCTION":
            fits_status = fn_Log(self.model, self.operation, parameters, values)
            print(f"Uploaad {self.sn_cover} into {self.operation}")
            if fits_status == True:
                QMessageBox.information(self, "FITs Message", "Data has been uploaded to FITs")
            else:
                QMessageBox.critical(self, "FITs Message", f"Data uploaded failed to FITs\nPlease manual key and contract developer Ext:7763\n{fits_status}")
        else:
            QMessageBox.information(self, "System Message", f"Data has been Store in Log file\n{self.LogPath}")
        
        self.MainstackedWidget.setCurrentIndex(3)
    
    def finish_cycle(self):
        self.clear_log()
        self.MainstackedWidget.setCurrentIndex(1)
        self.SNCoverValue.setFocus()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.showFullScreen()
    sys.exit(app.exec())    