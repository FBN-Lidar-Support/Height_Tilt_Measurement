from PyQt6.QtWidgets import QApplication, QMainWindow, QInputDialog, QMessageBox, QLineEdit
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPixmap
from PyQt6 import uic
from datetime import datetime, timedelta
from pathlib import Path
import json
import sys
import csv
import os
import configparser

from IL_sensors_cmd import Read_all_sensor_dual
from measurement import apply_sensor_offset, Test_OB_Height, Test_OB_Tilt, Test_OB_Relative
from fitsdll import fn_Handshake, fn_Log, fn_Query
from calibration_record import create_calibration_ini

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
        pcname = os.environ['COMPUTERNAME']
        print(pcname)
        self.MC = pcname
        
        self.load_config()

        os.makedirs(self.LogPath, exist_ok=True)
        self.clear_log()
        
        self.setting_update()
        
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

        self.Start_cal_Button.clicked.connect(self.show_countdown)
        
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        
        self.cal_timer = QTimer(self)
        self.cal_timer.timeout.connect(self.calibrate_timer_loop)

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

        self.Stop_Button.clicked.connect(self.logout)

    def load_config(self):
        self.config = configparser.ConfigParser()
        self.config_path = os.path.join(self.BASE_DIR, "Properties", "Config.ini")
        try:
            self.config.read(self.config_path)
            self.IP_1 = self.config["DEFAULT"].get("IP_1", "")
            self.PORT_1 = int(self.config["DEFAULT"].get("PORT_1", ""))
            self.IP_2 = self.config["DEFAULT"].get("IP_2", "")
            self.PORT_2 = int(self.config["DEFAULT"].get("PORT_2", ""))
            self.LogPath = self.config["DEFAULT"].get("LogPath", "")
            self.retry =  self.config["DEFAULT"].get("retry", "").strip().lower() == "true"
            
            self.type_SR = self.config["FITs"].get("SR", "").split(",")
            self.type_LR = self.config["FITs"].get("LR", "").split(",")
            self.model = self.config["FITs"].get("model", "")
            self.operation = self.config["FITs"].get("operationlist", "")
            
            self.spec_LR = {
                "Test_OB_Hight": {
                    "enable": self.config["LR"].get("Test_OB_Hight", "").strip().lower() == "true",
                    "nominal": self.config["Test_OB_Hight"].getfloat("LR_nominal", 0),
                    "tolerance": self.config["Test_OB_Hight"].getfloat("LR_tolerance", 0)
                    },
                "Test_OB_Relative": {
                    "enable": self.config["LR"].get("Test_OB_Relative", "").strip().lower() == "true",
                    "tolerance": self.config["Test_OB_Relative"].getfloat("LR_tolerance", 0.300)
                    },
                "Test_OB_Tilt": {
                    "enable": self.config["LR"].get("Test_OB_Tilt", "").strip().lower() == "true"
                    }
            }
            
            self.spec_SR = {
                "Test_OB_Hight": {
                    "enable": self.config["SR"].get("Test_OB_Hight", "").strip().lower() == "true",
                    "nominal": self.config["Test_OB_Hight"].getfloat("SR_nominal", 0),
                    "tolerance": self.config["Test_OB_Hight"].getfloat("SR_tolerance", 0)
                    },
                "Test_OB_Relative": {
                    "enable": self.config["SR"].get("Test_OB_Relative", "").strip().lower() == "true",
                    "tolerance": self.config["Test_OB_Relative"].getfloat("SR_tolerance", 0.300)
                    },
                "Test_OB_Tilt": {
                    "enable": self.config["SR"].get("Test_OB_Tilt", "").strip().lower() == "true"
                    }
            }
        except Exception as e:
            print(f"{e}\nPlease check config.ini")
            print("Close Program", f"{e}\nPlease check config.ini")
            quit()
        
        self.cal = configparser.ConfigParser()
        self.cal_path = os.path.join(self.BASE_DIR, "Properties", "Calibration.ini")
        if not os.path.exists(self.cal_path):
            create_calibration_ini(self.cal_path)
        self.offset_ALL = {}
        try:
            self.cal.read(self.cal_path)
            for key, value in self.cal._sections["OFFSET_ALL"].items():
                self.offset_ALL[key] = value
        except Exception as e:
            print(f"{e}\nPlease check config.ini")
            print("Close Program", f"{e}\nPlease check config.ini")
            quit()

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

        self.Raw_C1.setText("")
        self.Raw_C2.setText("")
        self.Raw_C3.setText("")
        self.Raw_B1.setText("")
        self.Raw_B2.setText("")
        self.Raw_B3.setText("")
        self.Raw_B4.setText("")
        self.Test1_Nominal.setText("")
        self.Test1_tolerance.setText("")
        self.Test1_Bench1_Value.setText("")
        self.Test1_Bench2_Value.setText("")
        self.Test1_Bench3_Value.setText("")
        self.Test1_Bench4_Value.setText("")
        self.Test1_Point_Result.setText("")
        self.Test1_Plane_Value.setText("")
        self.Test1_Plane_Delta.setText("")
        self.Test1_Plane_Result.setText("")
        self.Test1_Result.setText("")

        self.Test2_Tilt_plane.setText("")
        self.Test2_Pitch.setText("")
        self.Test2_Roll.setText("")
        self.Test2_Result.setText("")
        
        self.Test3_Tolerance.setText("")
        self.Test3_Bench1_Value.setText("")
        self.Test3_Bench2_Value.setText("")
        self.Test3_Front_AVG.setText("")
        self.Test3_Bench3_Value.setText("")
        self.Test3_Bench4_Value.setText("")
        self.Test3_Rear_AVG.setText("")
        self.Test3_Delta.setText("")
        self.Test3_Result.setText("")

        self.Final_Result.setText("")

    def setting_update(self):
        if self.retry == True:
            self.tries.setCurrentText("True")
        else:
            self.tries.setCurrentText("False")
        self.Log_Path.setText(self.LogPath)
        
        self.ip_1.setText(self.IP_1)
        self.port_1.setText(str(self.PORT_1))
        self.ip_2.setText(self.IP_2)
        self.port_2.setText(str(self.PORT_2))
        
        self.Toggle_LR_Test_OB_Height.setChecked(self.spec_LR["Test_OB_Hight"]["enable"])
        self.Test1_LR_nominal.setText(str(self.spec_LR["Test_OB_Hight"]["nominal"]))
        self.Test1_LR_tolerance.setText(str(self.spec_LR["Test_OB_Hight"]["tolerance"]))
        self.Toggle_LR_Test_OB_Relative.setChecked(self.spec_LR["Test_OB_Relative"]["enable"])
        self.Test2_LR_tolerance.setText(str(self.spec_LR["Test_OB_Relative"]["tolerance"]))
        self.Toggle_LR_Test_OB_Tilt.setChecked(self.spec_LR["Test_OB_Tilt"]["enable"])

        self.Toggle_SR_Test_OB_Height.setChecked(self.spec_SR["Test_OB_Hight"]["enable"])
        self.Test1_SR_nominal.setText(str(self.spec_SR["Test_OB_Hight"]["nominal"]))
        self.Test1_SR_tolerance.setText(str(self.spec_SR["Test_OB_Hight"]["tolerance"]))
        self.Toggle_SR_Test_OB_Relative.setChecked(self.spec_SR["Test_OB_Relative"]["enable"])
        self.Test2_SR_tolerance.setText(str(self.spec_SR["Test_OB_Relative"]["tolerance"]))
        self.Toggle_SR_Test_OB_Tilt.setChecked(self.spec_SR["Test_OB_Tilt"]["enable"])
        
        self.sensor_1.setText(str(self.offset_ALL["sensor_1"]))
        self.sensor_2.setText(str(self.offset_ALL["sensor_2"]))
        self.sensor_3.setText(str(self.offset_ALL["sensor_3"]))
        self.sensor_4.setText(str(self.offset_ALL["sensor_4"]))
        self.sensor_5.setText(str(self.offset_ALL["sensor_5"]))
        self.sensor_6.setText(str(self.offset_ALL["sensor_6"]))
        self.sensor_7.setText(str(self.offset_ALL["sensor_7"]))
        self.sensor_8.setText(str(self.offset_ALL["sensor_8"]))
        self.sensor_9.setText(str(self.offset_ALL["sensor_9"]))

    def select_mode(self):
        self.en = self.enLineEdit.text()
        if len(self.en) != 6:
            self.label_Error_login.setStyleSheet("color: red;")
            self.label_Error_login.setText("Invalid Employee number")
            return
        self.label_Error_login.setText("")
        password, ok = QInputDialog.getText(self, "Admin login", "Enter admin password:", QLineEdit.EchoMode.Password)
        if ok and password == "Admin123":
            self.MainstackedWidget.setCurrentIndex(4)
        else:
            QMessageBox.warning(self, "Asscess Denied", "Incorrect password.")

    def back_to_main(self):
        self.MainstackedWidget.setCurrentIndex(0)

    def save_setting(self):
        self.config.read(self.config_path)
        self.config.set("DEFAULT", "LogPath", self.Log_Path.text())
        self.config.set("DEFAULT", "IP_1", self.ip_1.text())
        self.config.set("DEFAULT", "PORT_1", self.port_1.text())
        self.config.set("DEFAULT", "IP_2", self.ip_2.text())
        self.config.set("DEFAULT", "PORT_2", self.port_2.text())
        self.config.set("DEFAULT", "retry", self.tries.currentText())
        
        self.config.set("LR", "Test_OB_Hight", (str(self.Toggle_LR_Test_OB_Height.isChecked())))
        self.config.set("Test_OB_Hight", "LR_nominal", self.Test1_LR_nominal.text())
        self.config.set("Test_OB_Hight", "LR_tolerance", self.Test1_LR_tolerance.text())
        self.config.set("SR", "Test_OB_Hight", (str(self.Toggle_SR_Test_OB_Height.isChecked())))
        self.config.set("Test_OB_Hight", "SR_nominal", self.Test1_SR_nominal.text())
        self.config.set("Test_OB_Hight", "SR_tolerance", self.Test1_SR_tolerance.text())
        
        self.config.set("LR", "Test_OB_Relative", (str(self.Toggle_LR_Test_OB_Relative.isChecked())))
        self.config.set("Test_OB_Relative", "LR_tolerance", self.Test2_LR_tolerance.text())
        self.config.set("SR", "Test_OB_Relative", (str(self.Toggle_SR_Test_OB_Relative.isChecked())))
        self.config.set("Test_OB_Relative", "SR_tolerance", self.Test2_SR_tolerance.text())
        
        self.config.set("LR", "Test_OB_Tilt", (str(self.Toggle_LR_Test_OB_Tilt.isChecked())))
        self.config.set("SR", "Test_OB_Tilt", (str(self.Toggle_SR_Test_OB_Tilt.isChecked())))
        
        with open(os.path.join(self.config_path), "w") as configfile:
            self.config.write(configfile)
        self.load_config()

    def show_countdown(self):
        self.sn_master = self.sn_master_cal.text()
        if not self.sn_master:
            QMessageBox.warning(self, "Start Calibration Deined", "Serial Master unit can not empty.")
            return
        try:
            self.count_value = 3
            self.Start_cal_Button.setEnabled(False)
            self.sn_master_cal.setEnabled(False)
            self.countdown_meg = QMessageBox(self)
            self.countdown_meg.setWindowTitle("Calibration")
            self.countdown_meg.setText(f"Calibration will start in {self.count_value} seconds")
            self.countdown_meg.setInformativeText(f"Please place Golden MASTER CAL from CMM and keep it stable")
            self.countdown_meg.setStandardButtons(QMessageBox.StandardButton.Cancel)
            self.countdown_meg.buttonClicked.connect(self.cancel_countdown)
            self.countdown_meg.show()
            self.countdown_timer.start(1000)
            
        except Exception as e:
            self.Start_cal_Button.setEnabled(True)
            self.sn_master_cal.setEnabled(True)
            QMessageBox.critical(self, "Countdown Error", str(e))
        
    def update_countdown(self):
        self.count_value -= 1
        if self.count_value > 0:
            self.countdown_meg.setText(f"Calibration will start in {self.count_value} seconds")
        else:
            self.countdown_timer.stop()
            self.countdown_meg.close()
            
            self.start_calibrate()
    
    def cancel_countdown(self):
        self.countdown_timer.stop()
        self.countdown_meg.close()
        self.Start_cal_Button.setEnabled(True)
        self.sn_master_cal.setEnabled(True)
        
    def start_calibrate(self):
        print("start_calibrate")
        try:
            self.sample_count = 100
            self.current_sample = 0
            self.cal_interval_ms = 500
            
            self.golden_section = "CALIBRATED_JIG"
            self.offset_section = "OFFSET_ALL"
            self.calibrate_sensors = [1, 2, 3, 4, 5, 6, 7, 8, 9]
            
            config = configparser.ConfigParser()
            config.read(self.config_path)
            
            if not config.has_section(self.golden_section):
                self.Start_cal_Button.setEnabled(True)
                self.sn_master_cal.setEnabled(True)
                QMessageBox.warning(self, "Calibration Error", f"Not found section {self.golden_section} in config.ini")
                return
            
            self.master_value = {}
            
            for sensor_id in self.calibrate_sensors:
                nominal_key = f"nominal_s{sensor_id}"
                if not config.has_option(self.golden_section, nominal_key):
                    self.Start_cal_Button.setEnabled(True)
                    self.sn_master_cal.setEnabled(True)
                    QMessageBox.warning(self, "Calibration Error", f"Not found {nominal_key} in [GOLDEN_{self.golden_section}]")
                    return
                
                dN_key = f"dN_s{sensor_id}"
                if not config.has_option(self.golden_section, dN_key):
                    self.Start_cal_Button.setEnabled(True)
                    self.sn_master_cal.setEnabled(True)
                    QMessageBox.warning(self, "Calibration Error", f"Not found {dN_key} in [GOLDEN_{self.golden_section}]")
                    return
                
                self.master_value[f"sensor_{sensor_id}"] = config.getfloat(self.golden_section, nominal_key) - config.getfloat(self.golden_section, dN_key)
                
            self.samples = {f"sensor_{sensor_id}": [] for sensor_id in self.calibrate_sensors}
            
            self.cal_timer.start(self.cal_interval_ms)
            
        except Exception as e:
            self.Start_cal_Button.setEnabled(True)
            self.sn_master_cal.setEnabled(True)
            QMessageBox.critical(self, "Calibration Error", str(e))

    def calibrate_timer_loop(self):
        try:
            raw_values = Read_all_sensor_dual(self.IP_1, self.PORT_1, self.IP_2, self.PORT_2)
            
            self.update_sensor_display(raw_values)
            
            for sensor_id in self.calibrate_sensors:
                key = f"sensor_{sensor_id}"
                
                if key not in raw_values:
                    self.cal_timer.stop()
                    self.Start_cal_Button.setEnabled(True)
                    self.sn_master_cal.setEnabled(True)
                    QMessageBox.warning(self, "Calibration Error", f"Missing raw value: {key}")
                    return
                self.samples[key].append(float(raw_values[key]))
            
            self.current_sample += 1
            self.progressBar.setValue(self.current_sample)
            
            if self.current_sample >= self.sample_count:
                self.cal_timer.stop()
                self.finish_calibration()
        except Exception as e:
            self.cal_timer.stop()
            self.Start_cal_Button.setEnabled(True)
            self.sn_master_cal.setEnabled(True)
            QMessageBox.critical(self, "Calibration Error", str(e))
            
    def finish_calibration(self):
        try:
            average_values = {}
            for key, values in self.samples.items():
                if len(values) == 0:
                    QMessageBox.warning(self, "Calibration Error", f"No sample data for {key}")
                    self.Start_cal_Button.setEnabled(True)
                    self.sn_master_cal.setEnabled(True)
                    return
                average_values[key] = sum(values) / len(values)
            # =========================
            # Calculate offset
            # offset = master - average_raw
            # =========================
            offsets = {}
            for key, avg_raw in average_values.items():
                master = self.master_value[key]
                offsets[key] = master - avg_raw
            # =========================
            # Save to Calibration.ini
            # =========================
            self.cal.read(self.cal_path)
            if not self.cal.has_section("CALIBRATION_INFO"):
                self.cal.add_section("CALIBRATION_INFO")
            if not self.cal.has_section(self.offset_section):
                self.cal.add_section(self.offset_section)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for key, offset in offsets.items():
                self.cal.set(self.offset_section, key, f"{offset:.6f}")

            self.cal.set("CALIBRATION_INFO", "last_calibrate", now)
            self.cal.set("CALIBRATION_INFO", "status", "OK")
            self.cal.set("CALIBRATION_INFO", "sample_count", str(self.sample_count))
            self.cal.set("CALIBRATION_INFO", "calibrate_by", str(self.en))
            self.cal.set("CALIBRATION_INFO", "calibrate_master", str(self.sn_master))

            with open(self.cal_path, "w") as file:
                self.cal.write(file)
            self.Start_cal_Button.setEnabled(True)
            self.sn_master_cal.setEnabled(True)
            self.sn_master_cal.setText("")
            QMessageBox.information(self, "Calibration Complete", f"Calibration {self.golden_section} complete\nSaved to Calibration.ini")
            self.load_config()
            self.setting_update()
            self.progressBar.setValue(0)
            
        except Exception as e:
            self.Start_cal_Button.setEnabled(True)
            self.sn_master_cal.setEnabled(True)
            QMessageBox.critical(self, "Save Calibration Error", str(e))
            
    def update_sensor_display(self, raw_values):
        label_map = {
            "sensor_1": self.curr_sensor1,
            "sensor_2": self.curr_sensor2,
            "sensor_3": self.curr_sensor3,
            "sensor_4": self.curr_sensor4,
            "sensor_5": self.curr_sensor5,
            "sensor_6": self.curr_sensor6,
            "sensor_7": self.curr_sensor7,
            "sensor_8": self.curr_sensor8,
            "sensor_9": self.curr_sensor9,
        }
        for sensor_key, label in label_map.items():
            value = raw_values.get(sensor_key)
            if value is None:
                label.setText("---")
            else:
                label.setText(f"{float(value):.3f}")

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

    def loading_image(self):
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
        self.mode = self.pro_mode.currentText()
        
        if self.mode == ("BUY-OFF"):
            self.model = "Buy-off Golden Unit"
            self.Mode_text.setText(self.mode)
            print("Program mode:\t", self.mode)
            print("Model:\t",self.model)
            print("Serial:\t",self.sn_cover)
            PN = self.config["GOLDEN-UNIT"].get(self.sn_cover, "")
            if not PN:
                QMessageBox.critical(self, "Golden config not found", "Serial Golden unit not found\nPlease contact Engineer to add Golden unit")
                return
            print("Retry:\t", self.retry)
            print("Part Number:\t", PN)
            self.operation = self.sn_cover[1:3] + self.sn_cover[7:-2] + "G"
            print("Operation:\t", self.operation)

        else:
            self.model = self.config["FITs"].get("model", "")
            self.operation = self.config["FITs"].get("operationlist", "")
            print("Program mode:\t", self.mode)
            print("Model:\t",self.model)
            print("Serial:\t",self.sn_cover)
            self.Mode_text.setText(self.mode)
            fits_status = fn_Handshake(self.model, self.operation, self.sn_cover)
            if fits_status != True:
                self.Errorlabel.setText(fits_status)
                self.SNCoverValue.setText("")
                self.SNBenchValue.setText("")
                self.SNCoverValue.setFocus()
                return
            
            self.Errorlabel.setText("")
            PN = fn_Query("*", "*", self.sn_cover, "#Part_no")
            print("Part Number:\t", PN)
            print("Operation:\t", self.operation)
            try:
                golden_list = json.loads(self.config["FITs"].get(PN, "{}"))
                if golden_list:
                    print(golden_list)
                    for key, value in golden_list.items():
                        print(f"Role: {key}, Count: {value}")
                        Result, endtime = fn_Query("*", f"{self.operation}G", key, "Result;End datetime").split(";")
                        print("Result:\t", Result)
                        print("endtime:\t", endtime)
                        if Result and value:
                            endtime = datetime.strptime(endtime, "%d %b %Y %H:%M:%S:%f")
                            if Result != value:
                                QMessageBox.critical(self, "Golden unit Error", "Golden unit result not match")
                                return
                            if datetime.now() >= endtime:
                                QMessageBox.critical(self, "Buy-off expired", f"Please buy-off Golden unit {key}")
                                return
                        else:
                            QMessageBox.warning(self, "Buy-off Golden Unit", f"Please Buy-off Golden {value} Unit SN: {key} at {self.operation}G")
                            return    
            except KeyError as e:
                print(f"ERROR: {e}")
                pass
            
        if PN in self.type_LR:
            self.product_type = "LONG RANGE"
            self.lineEdit_Type.setText(self.product_type)
            prefix = "LR"
            self.spec = self.spec_LR
        elif PN in self.type_SR:
            self.product_type = "SHORT RANGE"
            self.lineEdit_Type.setText(self.product_type)
            prefix = "SR"
            self.spec = self.spec_SR
        else:
            QMessageBox.critical(self, "Invalid part number", "Unknow Part number please contact Engineer to add new part number to config file.")
            return
        
        self.loading_image()

        self.measure_axis = []
        for key, value in self.config._sections["SENSOR_POSITION"].items():
            self.measure_axis.append(value.split(","))
        self.list_sensors = []
        for v in self.config[f"{prefix}"].get("list_sensors", "").split(","):
            self.list_sensors.append(int(v)-1)

        QTimer.singleShot(100, self.mainprocess)

    def mainprocess(self):
        print("---------- mainprocess ----------")
        if self.retry == True:
            self.retryButton.show()
        else:
            self.retryButton.hide()
            
        self.MainstackedWidget.setCurrentIndex(2)
        self.lineEdit_Operator.setText(self.en)
        self.lineEdit_Operation.setText(self.operation)
        self.lineEdit_Station.setText(self.MC)
        self.lineEdit_Serial.setText(self.sn_cover)
        self.lineEdit_Serial_2.setText(self.sn_bench)

        raw_value = Read_all_sensor_dual(self.IP_1, self.PORT_1, self.IP_2, self.PORT_2)
        if raw_value is False:
            print("Can not read sensor\nPlease check IL-Sensor power")
            QMessageBox.critical(self, "IL Sensor ERROR", "Can not read sensor\nPlease check IL-Sensor power")
            quit()

        raw_value = list(raw_value.values())
        if any(abs(float(value)) > 999 for value in [raw_value[i] for i in self.list_sensors]):
            QMessageBox.warning(self, "Sensor out limit", "Please check Sensor or Unit that place in fixture")
            self.MainstackedWidget.setCurrentIndex(1)
            self.SNCoverValue.setFocus()
            return

        ##############################################################################        
        sensor_values = apply_sensor_offset(raw_value, self.cal)
        print("Raw_sensor_values_num:\t", sensor_values)
        ##############################################################################
        sensor_values_str = [f"{x:.3f}" for x in sensor_values]
        print("Raw_sensor_values:\t", sensor_values_str)
        self.Raw_B1.setText(sensor_values_str[3])
        self.Raw_B2.setText(sensor_values_str[4])
        self.Raw_B3.setText(sensor_values_str[5])
        self.Raw_B4.setText(sensor_values_str[6])

        if self.product_type == "SHORT RANGE":
            if self.spec_SR["Test_OB_Hight"]["enable"]:
                test1_result = Test_OB_Height(measure_axis= self.measure_axis, spec= self.spec_SR["Test_OB_Hight"], sensor_values= sensor_values, product_type= self.product_type)
            if self.spec_SR["Test_OB_Tilt"]["enable"]:
                test2_result = Test_OB_Tilt(measure_axis=self.measure_axis, sensor_values= sensor_values, product_type= self.product_type)
            if self.spec_SR["Test_OB_Relative"]["enable"]:
                test3_result = Test_OB_Relative(sensor_value= sensor_values, tolerance= self.spec_SR["Test_OB_Relative"]["tolerance"])
            self.Raw_C1.setText(sensor_values_str[7])
            self.Raw_C2.setText(sensor_values_str[8])
            self.Raw_C3.setText("N/A")
        else:
            if self.spec_LR["Test_OB_Hight"]["enable"]:
                test1_result = Test_OB_Height(measure_axis = self.measure_axis, spec= self.spec_LR["Test_OB_Hight"], sensor_values= sensor_values, product_type= self.product_type)
            if self.spec_LR["Test_OB_Tilt"]["enable"]:
                test2_result = Test_OB_Tilt(measure_axis = self.measure_axis, sensor_values= sensor_values, product_type= self.product_type)
            if self.spec_LR["Test_OB_Relative"]["enable"]:
                test3_result = Test_OB_Relative(sensor_value = sensor_values, tolerance= self.spec_LR["Test_OB_Relative"]["tolerance"])
            self.Raw_C1.setText(sensor_values_str[0])
            self.Raw_C2.setText(sensor_values_str[1])
            self.Raw_C3.setText(sensor_values_str[2])

        ########## RESULT Test_OB_Hight ##########
        self.Test1_Nominal.setText(str(test1_result["limits"]["nominal"]))
        self.Test1_tolerance.setText(str(test1_result["limits"]["tolerance"]))
        self.Test1_Bench1_Value.setText(str(test1_result["point_results"][0]["height"]))
        self.Test1_Delta_Bench1.setText(str(test1_result["point_results"][0]["deviation"]))
        if not test1_result["point_results"][0]["result"]:
            self.Test1_Bench1_Value.setStyleSheet("background-color: red; color: white;")
            self.Test1_Delta_Bench1.setStyleSheet("background-color: red; color: white;")
        else:
            self.Test1_Bench1_Value.setStyleSheet("")
            self.Test1_Delta_Bench1.setStyleSheet("") 
        self.Test1_Bench2_Value.setText(str(test1_result["point_results"][1]["height"]))
        self.Test1_Delta_Bench2.setText(str(test1_result["point_results"][1]["deviation"]))
        if not test1_result["point_results"][1]["result"]:
            self.Test1_Bench2_Value.setStyleSheet("background-color: red; color: white;")
            self.Test1_Delta_Bench2.setStyleSheet("background-color: red; color: white;")
        else:
            self.Test1_Bench2_Value.setStyleSheet("")
            self.Test1_Delta_Bench2.setStyleSheet("")
        self.Test1_Bench3_Value.setText(str(test1_result["point_results"][2]["height"]))
        self.Test1_Delta_Bench3.setText(str(test1_result["point_results"][2]["deviation"]))
        if not test1_result["point_results"][2]["result"]:
            self.Test1_Bench3_Value.setStyleSheet("background-color: red; color: white;")
            self.Test1_Delta_Bench3.setStyleSheet("background-color: red; color: white;")
        else:
            self.Test1_Bench3_Value.setStyleSheet("")
            self.Test1_Delta_Bench3.setStyleSheet("")
        self.Test1_Bench4_Value.setText(str(test1_result["point_results"][3]["height"]))
        self.Test1_Delta_Bench4.setText(str(test1_result["point_results"][3]["deviation"]))
        if not test1_result["point_results"][3]["result"]:
            self.Test1_Bench4_Value.setStyleSheet("background-color: red; color: white;")
            self.Test1_Delta_Bench4.setStyleSheet("background-color: red; color: white;")
        else:
            self.Test1_Bench4_Value.setStyleSheet("")
            self.Test1_Delta_Bench4.setStyleSheet("")
        self.Test1_Point_Result.setText(str(test1_result["point_result"]))
        if test1_result["point_result"] == "FAIL":
            self.Test1_Point_Result.setStyleSheet("background-color: red; color: white;")
        else:
            self.Test1_Point_Result.setStyleSheet("background-color: rgb(0, 255, 127);")
        
        self.Test1_Plane_Value.setText(str(test1_result["ob_plane_height"]))
        self.Test1_Plane_Delta.setText(str(test1_result["plane_deviation"]))
        self.Test1_Plane_Result.setText(str(test1_result["plane_result"]))
        if test1_result["plane_result"] == "FAIL":
            self.Test1_Plane_Value.setStyleSheet("background-color: red; color: white;")
            self.Test1_Plane_Delta.setStyleSheet("background-color: red; color: white;")
            self.Test1_Plane_Result.setStyleSheet("background-color: red; color: white;") 
        else:
            self.Test1_Plane_Value.setStyleSheet("")
            self.Test1_Plane_Delta.setStyleSheet("")
            self.Test1_Plane_Result.setStyleSheet("background-color: rgb(0, 255, 127);")
        self.Test1_Result.setText(test1_result["result"])
        if test1_result["result"] == "FAIL":
            self.Test1_Result.setStyleSheet("background-color: red; color: white;")
        else:
            self.Test1_Result.setStyleSheet("background-color: rgb(0, 255, 127);")
        
        ########## RESULT Test_OB_Tilt ##########
        self.Test2_Tilt_plane.setText(str(test2_result["tilt_angle"]))
        Pitch_num = test2_result["pitch"]
        Pitch_d = test2_result["pitch_direction"] 
        self.Test2_Pitch.setText(f"{Pitch_d} | {Pitch_num}")
        roll_num = test2_result["roll"]
        roll_d = test2_result["roll_direction"] 
        self.Test2_Roll.setText(f"{roll_d} | {roll_num}")
        self.Test2_Result.setText("N/A")
        
        ########## RESULT Test_OB_Relative ##########
        self.Test3_Tolerance.setText(str(test3_result["limit"]))
        self.Test3_Bench1_Value.setText(str(test3_result["bench_pts"][0]))
        self.Test3_Bench2_Value.setText(str(test3_result["bench_pts"][1]))
        self.Test3_Front_AVG.setText(str(test3_result["front_AVG"]))
        self.Test3_Bench3_Value.setText(str(test3_result["bench_pts"][2]))
        self.Test3_Bench4_Value.setText(str(test3_result["bench_pts"][3]))
        self.Test3_Rear_AVG.setText(str(test3_result["rear_AVG"]))
        
        self.Test3_Delta.setText(str(test3_result["deviation"]))
        self.Test3_Result.setText(test3_result["result"])
        if test3_result["result"] == "FAIL":
            self.Test3_Delta.setStyleSheet("background-color: red; color: white;")
            self.Test3_Result.setStyleSheet("background-color: red; color: white;")
        else:
            self.Test3_Delta.setStyleSheet("")
            self.Test3_Result.setStyleSheet("background-color: rgb(0, 255, 127);")
        
        self.df = {
            "EN": self.en,
            "SN": self.sn_cover,
            "SN OB": self.sn_bench,
            "Time Stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "Product Type": self.product_type,
            "Raw Cover 1": self.Raw_C1.text(),
            "Raw Cover 2": self.Raw_C2.text(),
            "Raw Cover 3": self.Raw_C3.text(),
            "Raw Bench 1": self.Raw_B1.text(),
            "Raw Bench 2": self.Raw_B2.text(),
            "Raw Bench 3": self.Raw_B3.text(),
            "Raw Bench 4": self.Raw_B4.text(),
            "Bench offset 1": self.Test1_Bench1_Value.text(),
            "Bench offset 2": self.Test1_Bench2_Value.text(),
            "Bench offset 3": self.Test1_Bench3_Value.text(),
            "Bench offset 4": self.Test1_Bench4_Value.text(),
            "Delta Bench 1": self.Test1_Delta_Bench1.text(),
            "Delta Bench 2": self.Test1_Delta_Bench2.text(),
            "Delta Bench 3": self.Test1_Delta_Bench3.text(),
            "Delta Bench 4": self.Test1_Delta_Bench4.text(),
            "Bench plane offset": self.Test1_Plane_Value.text(),
            "Delta Plane": self.Test1_Plane_Delta.text(),
            "OB Height Result": self.Test1_Result.text(),
            "Tilt angle between planes": self.Test2_Tilt_plane.text(),
            "Tilt Pitch direction": self.Test2_Pitch.text(),
            "Tilt Roll direction": self.Test2_Roll.text(),
            "OB Tilt Result": self.Test2_Result.text(),
            "OB Front AVG": self.Test3_Front_AVG.text(), 
            "OB Back AVG": self.Test3_Rear_AVG.text(),
            "Delta OB Relative": self.Test3_Delta.text(),
            "OB Relative Result": self.Test3_Result.text(),
            }
        
        final_result = (self.df["OB Relative Result"] == "PASS" and self.df["OB Height Result"] == "PASS")
        self.df["Result"] = "PASS" if final_result else "FAIL" 
        self.Final_Result.setText(self.df["Result"])
        if not final_result:
            self.df["Remark"] = "Plase Confirm Unit with OGP"
            self.Final_Result.setStyleSheet("background-color: red; color: white;")
        else:
            self.Final_Result.setStyleSheet("background-color: rgb(0, 255, 127);")
        print("="*20 ," Result ", "="*20)
        for key, value in self.df.items():
            print(f"{key}\t{value}")

    def record_results(self):
        now = self.df["Time Stamp"]
        if self.mode == "BUY-OFF":
            self.df["Golden Unit S/N"] = self.df.pop("SN")
            now_buyoff = datetime.now()
            start_day = datetime.strptime("07:00","%H:%M").time()
            end_day = datetime.strptime("19:00","%H:%M").time()
            if start_day <= datetime.now().time() < end_day:
                print("SHIFT DAY")
                buy_off_end = now_buyoff.replace(hour=19,minute=0,second=0,microsecond=0)
            else:
                print("SHIFT NIGHT")
                buy_off_end = now_buyoff.replace(hour=7,minute=0,second=0,microsecond=0)+ timedelta(days=1)
            self.df.update(
                {
                    "Buy off Datetime": datetime.strptime(now, "%Y-%m-%d %H:%M:%S.%f").strftime("%d %b %Y %H:%M:%S:%f")[:-3],
                    "End datetime": buy_off_end.strftime("%d %b %Y %H:%M:%S:%f")[:-3],
                }
            )
        now = now.replace(":","-").split(".")[0]
        filepath = os.path.join(self.LogPath, f"{self.sn_cover}_{now}.csv")
        with open(filepath, mode='w', encoding="utf-8", newline='') as file:
            writer = csv.writer(file)
            writer.writerow(self.df.keys())  # Write header
            writer.writerow(self.df.values())  # Write values
        
        if self.df["Result"] == "FAIL":
            self.df["Defect code"] = "IND-024"

        parameters = ";".join(self.df.keys())
        values = ";".join(self.df.values())
        
        if self.mode == "PRODUCTION" or self.mode == "BUY-OFF":
            fits_status = fn_Log(self.model, self.operation, parameters, values)
            if fits_status == True:
                print(f"Uploaad {self.sn_cover} into {self.operation}")
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
    main_window.showMaximized()
    sys.exit(app.exec())    