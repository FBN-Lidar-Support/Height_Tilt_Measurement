import os
import math
import configparser
from datetime import datetime
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication,QWidget,QPushButton,QLabel,QMessageBox,QGridLayout,QVBoxLayout,QGroupBox,QProgressBar
from IL_sensors_cmd import Read_all_sensor_dual
from measurement import apply_sensor_offset
class RepeatabilityTestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Repeatability Test - Sensor 1 to 9")
        self.resize(900, 620)
        # =========================
        # Setting
        # =========================
        self.sample_count = 1000
        self.interval_ms = 20
        self.repeat_sensors = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        # spec control 
        self.tolerance_width = 0.07
        self.log_dir = r"C:\Projects\Cells_DR\Logs"
        self.excel_filename = "repeatability_report.xlsx"
        self.cal = configparser.ConfigParser()
        self.cal.read("C:\Projects\Cells_DR\Properties\Calibration.ini")
        self.IP_1 = "169.254.148.227"
        self.PORT_1 = 64000
        self.IP_2 = "169.254.148.228"
        self.PORT_2 = 64000
        # =========================
        # Timer
        # =========================
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.repeat_timer = QTimer(self)
        self.repeat_timer.timeout.connect(self.repeat_loop)
        # =========================
        # UI
        # =========================
        self.start_button = QPushButton("Start Repeat Test")
        self.start_button.clicked.connect(self.start_countdown)
        self.status_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.raw_labels = {}
        self.result_labels = {}
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.start_button)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.progress_bar)
        # =========================
        # Raw value group
        # =========================
        raw_group = QGroupBox("Current Raw Sensor Value")
        raw_layout = QGridLayout()
        for row, sensor_id in enumerate(self.repeat_sensors):
            sensor_key = f"sensor_{sensor_id}"
            raw_layout.addWidget(QLabel(f"Sensor {sensor_id}:"), row, 0)
            raw_label = QLabel("---")
            self.raw_labels[sensor_key] = raw_label
            raw_layout.addWidget(raw_label, row, 1)
            raw_layout.addWidget(QLabel("mm"), row, 2)
        raw_group.setLayout(raw_layout)
        main_layout.addWidget(raw_group)
        # =========================
        # Result group
        # =========================
        result_group = QGroupBox("Repeatability Result")
        result_layout = QGridLayout()
        headers = [
            "Sensor",
            "AVG",
            "MIN",
            "MAX",
            "RANGE",
            "STD",
            "6SIGMA",
            "%TOL",
        ]
        for col, header in enumerate(headers):
            result_layout.addWidget(QLabel(header), 0, col)
        for row, sensor_id in enumerate(self.repeat_sensors, start=1):
            sensor_key = f"sensor_{sensor_id}"
            result_layout.addWidget(QLabel(f"Sensor {sensor_id}"), row, 0)
            self.result_labels[sensor_key] = {
                "avg": QLabel("-"),
                "min": QLabel("-"),
                "max": QLabel("-"),
                "range": QLabel("-"),
                "std": QLabel("-"),
                "six_sigma": QLabel("-"),
                "percent_tol": QLabel("-"),
            }
            result_layout.addWidget(self.result_labels[sensor_key]["avg"], row, 1)
            result_layout.addWidget(self.result_labels[sensor_key]["min"], row, 2)
            result_layout.addWidget(self.result_labels[sensor_key]["max"], row, 3)
            result_layout.addWidget(self.result_labels[sensor_key]["range"], row, 4)
            result_layout.addWidget(self.result_labels[sensor_key]["std"], row, 5)
            result_layout.addWidget(self.result_labels[sensor_key]["six_sigma"], row, 6)
            result_layout.addWidget(self.result_labels[sensor_key]["percent_tol"], row, 7)
        result_group.setLayout(result_layout)
        main_layout.addWidget(result_group)
        self.setLayout(main_layout)
    # =========================================================
    # Countdown
    # =========================================================
    def start_countdown(self):
        try:
            self.countdown_value = 3
            self.start_button.setEnabled(False)
            self.countdown_msg = QMessageBox(self)
            self.countdown_msg.setWindowTitle("Repeatability Test")
            self.countdown_msg.setText(
                f"Repeatability test will start in {self.countdown_value} seconds"
            )
            self.countdown_msg.setInformativeText(
                "Please place the Golden part and keep it stable."
            )
            self.countdown_msg.setStandardButtons(QMessageBox.StandardButton.Cancel)
            self.countdown_msg.buttonClicked.connect(self.cancel_countdown)
            self.countdown_msg.show()
            self.countdown_timer.start(1000)
        except Exception as e:
            self.start_button.setEnabled(True)
            QMessageBox.critical(self, "Countdown Error", str(e))
    def update_countdown(self):
        self.countdown_value -= 1
        if self.countdown_value > 0:
            self.countdown_msg.setText(
                f"Repeatability test will start in {self.countdown_value} seconds"
            )
        else:
            self.countdown_timer.stop()
            self.countdown_msg.close()
            self.start_repeat_test()
    def cancel_countdown(self):
        self.countdown_timer.stop()
        self.countdown_msg.close()
        self.start_button.setEnabled(True)
        self.status_label.setText("Canceled")
    # =========================================================
    # Repeat Test
    # =========================================================
    def start_repeat_test(self):
        try:
            self.current_sample = 0
            self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.samples = {
                f"sensor_{sensor_id}": []
                for sensor_id in self.repeat_sensors
            }
            # เก็บ raw data ทุก sample
            self.raw_records = []
            self.progress_bar.setValue(0)
            self.status_label.setText(f"Repeat Test... 0/{self.sample_count}")
            self.repeat_timer.start(self.interval_ms)
        except Exception as e:
            self.start_button.setEnabled(True)
            QMessageBox.critical(self, "Repeat Test Error", str(e))
    def repeat_loop(self):
        dict_measured_values = {}
        try:
            raw_values = Read_all_sensor_dual(self.IP_1, self.PORT_1, self.IP_2, self.PORT_2)
            raw_values = list(raw_values.values())
            measured_values = apply_sensor_offset(raw_values, self.cal)
            for idx, v in enumerate(measured_values):
                dict_measured_values[f"sensor_{idx+1}"] = v           
            self.update_raw_display(dict_measured_values)
            raw_record = {
                "run_id": self.run_id,
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "sample_no": self.current_sample + 1,
            }
            for sensor_id in self.repeat_sensors:
                key = f"sensor_{sensor_id}"
                if key not in dict_measured_values:
                    self.stop_repeat_with_error(f"Missing raw value: {key}")
                    return
                value = dict_measured_values[key]
                if value is None or str(value).strip() in ["", "-", "None"]:
                    self.stop_repeat_with_error(f"{key} value is empty")
                    return
                try:
                    value_float = float(value)
                except ValueError:
                    self.stop_repeat_with_error(
                        f"{key} cannot convert to float: {value}"
                    )
                    return
                self.samples[key].append(value_float)
                raw_record[key] = value_float
            self.raw_records.append(raw_record)
            self.current_sample += 1
            self.status_label.setText(
                f"Repeat Test... {self.current_sample}/{self.sample_count}"
            )
            self.progress_bar.setValue(
                int(self.current_sample / self.sample_count * 100)
            )
            if self.current_sample >= self.sample_count:
                self.repeat_timer.stop()
                self.finish_repeat_test()
        except Exception as e:
            self.repeat_timer.stop()
            self.start_button.setEnabled(True)
            QMessageBox.critical(self, "Repeat Test Error", str(e))
    def stop_repeat_with_error(self, message):
        self.repeat_timer.stop()
        self.start_button.setEnabled(True)
        self.status_label.setText("Error")
        QMessageBox.warning(self, "Repeat Test Error", message)
    def finish_repeat_test(self):
        try:
            result = {}
            for key, values in self.samples.items():
                avg_value = sum(values) / len(values)
                min_value = min(values)
                max_value = max(values)
                range_value = max_value - min_value
                variance = sum((x - avg_value) ** 2 for x in values) / len(values)
                std_value = math.sqrt(variance)
                six_sigma = 6 * std_value
                if self.tolerance_width > 0:
                    percent_tol = (six_sigma / self.tolerance_width) * 100
                else:
                    percent_tol = 0
                result[key] = {
                    "run_id": self.run_id,
                    "avg": avg_value,
                    "min": min_value,
                    "max": max_value,
                    "range": range_value,
                    "std": std_value,
                    "six_sigma": six_sigma,
                    "percent_tol": percent_tol,
                    "count": len(values),
                }
            self.show_result(result)
            self.save_report_to_excel(result)
            self.status_label.setText("Repeat Test Complete")
            self.progress_bar.setValue(100)
            self.start_button.setEnabled(True)
            QMessageBox.information(
                self,
                "Repeat Test Complete",
                "Repeatability test complete.\nSaved to Excel with Summary and RawData sheets.",
            )
        except Exception as e:
            self.start_button.setEnabled(True)
            QMessageBox.critical(self, "Finish Repeat Test Error", str(e))
    # =========================================================
    # UI update
    # =========================================================
    def update_raw_display(self, raw_values):
        for sensor_key, label in self.raw_labels.items():
            value = raw_values.get(sensor_key)
            label.setText(self.format_sensor_value(value))
    def show_result(self, result):
        for sensor_key, r in result.items():
            if sensor_key not in self.result_labels:
                continue
            self.result_labels[sensor_key]["avg"].setText(f"{r['avg']:.4f}")
            self.result_labels[sensor_key]["min"].setText(f"{r['min']:.4f}")
            self.result_labels[sensor_key]["max"].setText(f"{r['max']:.4f}")
            self.result_labels[sensor_key]["range"].setText(f"{r['range']:.4f}")
            self.result_labels[sensor_key]["std"].setText(f"{r['std']:.4f}")
            self.result_labels[sensor_key]["six_sigma"].setText(f"{r['six_sigma']:.4f}")
            self.result_labels[sensor_key]["percent_tol"].setText(
                f"{r['percent_tol']:.2f}%"
            )
    def format_sensor_value(self, value):
        if value is None or str(value).strip() in ["", "-", "None"]:
            return "---"
        try:
            return f"{float(value):.3f}"
        except ValueError:
            return "---"
    # =========================================================
    # Save Excel Report
    # =========================================================
    def save_report_to_excel(self, result):
        os.makedirs(self.log_dir, exist_ok=True)
        excel_path = os.path.join(self.log_dir, self.excel_filename)
        if os.path.isfile(excel_path):
            wb = load_workbook(excel_path)
        else:
            wb = Workbook()
            default_sheet = wb.active
            wb.remove(default_sheet)
            wb.create_sheet("Summary")
            wb.create_sheet("RawData")
            self.setup_summary_sheet(wb["Summary"])
            self.setup_rawdata_sheet(wb["RawData"])
        if "Summary" not in wb.sheetnames:
            ws_summary = wb.create_sheet("Summary")
            self.setup_summary_sheet(ws_summary)
        else:
            ws_summary = wb["Summary"]
        if "RawData" not in wb.sheetnames:
            ws_raw = wb.create_sheet("RawData")
            self.setup_rawdata_sheet(ws_raw)
        else:
            ws_raw = wb["RawData"]
        self.append_summary_sheet(ws_summary, result)
        self.append_rawdata_sheet(ws_raw)
        self.auto_adjust_width(ws_summary)
        self.auto_adjust_width(ws_raw)
        wb.save(excel_path)
    def setup_summary_sheet(self, ws):
        headers = [
            "Run ID",
            "DateTime",
            "Sensor",
            "Count",
            "AVG",
            "MIN",
            "MAX",
            "RANGE",
            "STD",
            "6SIGMA",
            "%TOL",
            "Tolerance Width",
        ]
        ws.append(headers)
        self.style_header(ws)
    def setup_rawdata_sheet(self, ws):
        headers = [
            "Run ID",
            "DateTime",
            "Sample No",
        ]
        for sensor_id in self.repeat_sensors:
            headers.append(f"Sensor {sensor_id}")
        ws.append(headers)
        self.style_header(ws)
    def append_summary_sheet(self, ws, result):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for sensor_key, r in result.items():
            ws.append([
                self.run_id,
                now,
                sensor_key,
                r["count"],
                round(r["avg"], 6),
                round(r["min"], 6),
                round(r["max"], 6),
                round(r["range"], 6),
                round(r["std"], 6),
                round(r["six_sigma"], 6),
                round(r["percent_tol"], 3),
                self.tolerance_width,
            ])
    def append_rawdata_sheet(self, ws):
        for record in self.raw_records:
            row = [
                record["run_id"],
                record["datetime"],
                record["sample_no"],
            ]
            for sensor_id in self.repeat_sensors:
                key = f"sensor_{sensor_id}"
                value = record.get(key, "")
                if value == "":
                    row.append("")
                else:
                    row.append(round(float(value), 6))
            ws.append(row)
    def style_header(self, ws):
        header_fill = PatternFill("solid", fgColor="D9EAF7")
        header_font = Font(bold=True)
        thin = Side(border_style="thin", color="BFBFBF")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = Border(top=thin, left=thin, right=thin, bottom=thin)
        ws.freeze_panes = "A2"
    def auto_adjust_width(self, ws):
        for column_cells in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column_cells[0].column)
            for cell in column_cells:
                value = cell.value
                if value is None:
                    continue
                max_length = max(max_length, len(str(value)))
            adjusted_width = min(max_length + 2, 22)
            ws.column_dimensions[column_letter].width = adjusted_width

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = RepeatabilityTestWindow()
    window.show()
    sys.exit(app.exec())