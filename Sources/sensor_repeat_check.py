import csv
import os
import math
from datetime import datetime
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QApplication,QWidget,QPushButton,QLabel,QMessageBox,QGridLayout,QVBoxLayout,QGroupBox,QProgressBar)
from IL_sensors_cmd import Read_all_sensor_dual

class RepeatabilityTestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.IP_1 = "169.254.148.227"
        self.PORT_1 = 64000
        self.IP_2 = "169.254.148.228"
        self.PORT_2 = 64000
        self.setWindowTitle("Repeatability Test - Sensor 8 / 9")
        self.resize(520, 360)
        # =========================
        # Setting
        # =========================
        self.sample_count = 100
        self.interval_ms = 20
        self.repeat_sensors = [8, 9]
        self.log_dir = r"C:\Projects\Cells_DR\Logs"
        self.log_filename = "repeatability_sensor_8_9.csv"
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
        self.s8_raw_label = QLabel("---")
        self.s9_raw_label = QLabel("---")
        self.s8_avg_label = QLabel("-")
        self.s8_min_label = QLabel("-")
        self.s8_max_label = QLabel("-")
        self.s8_range_label = QLabel("-")
        self.s8_std_label = QLabel("-")
        self.s9_avg_label = QLabel("-")
        self.s9_min_label = QLabel("-")
        self.s9_max_label = QLabel("-")
        self.s9_range_label = QLabel("-")
        self.s9_std_label = QLabel("-")
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.start_button)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.progress_bar)
        raw_group = QGroupBox("Current Raw Sensor Value")
        raw_layout = QGridLayout()
        raw_layout.addWidget(QLabel("Sensor 8:"), 0, 0)
        raw_layout.addWidget(self.s8_raw_label, 0, 1)
        raw_layout.addWidget(QLabel("mm"), 0, 2)
        raw_layout.addWidget(QLabel("Sensor 9:"), 1, 0)
        raw_layout.addWidget(self.s9_raw_label, 1, 1)
        raw_layout.addWidget(QLabel("mm"), 1, 2)
        raw_group.setLayout(raw_layout)
        main_layout.addWidget(raw_group)
        result_group = QGroupBox("Repeatability Result")
        result_layout = QGridLayout()
        headers = ["Sensor", "AVG", "MIN", "MAX", "RANGE", "STD"]
        for col, header in enumerate(headers):
            result_layout.addWidget(QLabel(header), 0, col)
        result_layout.addWidget(QLabel("Sensor 8"), 1, 0)
        result_layout.addWidget(self.s8_avg_label, 1, 1)
        result_layout.addWidget(self.s8_min_label, 1, 2)
        result_layout.addWidget(self.s8_max_label, 1, 3)
        result_layout.addWidget(self.s8_range_label, 1, 4)
        result_layout.addWidget(self.s8_std_label, 1, 5)
        result_layout.addWidget(QLabel("Sensor 9"), 2, 0)
        result_layout.addWidget(self.s9_avg_label, 2, 1)
        result_layout.addWidget(self.s9_min_label, 2, 2)
        result_layout.addWidget(self.s9_max_label, 2, 3)
        result_layout.addWidget(self.s9_range_label, 2, 4)
        result_layout.addWidget(self.s9_std_label, 2, 5)
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
                "Please place the Golden LR and keep it stable."
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
            self.samples = {
                f"sensor_{sensor_id}": []
                for sensor_id in self.repeat_sensors
            }
            self.progress_bar.setValue(0)
            self.status_label.setText(f"Repeat Test... 0/{self.sample_count}")
            self.repeat_timer.start(self.interval_ms)
        except Exception as e:
            self.start_button.setEnabled(True)
            QMessageBox.critical(self, "Repeat Test Error", str(e))
    def repeat_loop(self):
        raw = Read_all_sensor_dual(self.IP_1, self.PORT_1, self.IP_2, self.PORT_2)
        raw_values = list(raw.values())[-2:]
        try:
            self.update_raw_display(raw_values)
            for sensor_id in self.repeat_sensors:
                key = f"sensor_{sensor_id}"
                if key not in raw_values:
                    self.stop_repeat_with_error(f"Missing raw value: {key}")
                    return
                value = raw_values[key]
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
                result[key] = {
                    "avg": avg_value,
                    "min": min_value,
                    "max": max_value,
                    "range": range_value,
                    "std": std_value,
                    "count": len(values),
                }
            self.show_result(result)
            self.save_result_to_csv(result)
            self.status_label.setText("Repeat Test Complete")
            self.progress_bar.setValue(100)
            self.start_button.setEnabled(True)
            QMessageBox.information(
                self,
                "Repeat Test Complete",
                "Repeatability test complete. Result saved to CSV.",
            )
        except Exception as e:
            self.start_button.setEnabled(True)
            QMessageBox.critical(self, "Finish Repeat Test Error", str(e))
    # =========================================================
    # UI update
    # =========================================================
    def update_raw_display(self, raw_values):
        s8 = raw_values.get("sensor_8")
        s9 = raw_values.get("sensor_9")
        self.s8_raw_label.setText(self.format_sensor_value(s8))
        self.s9_raw_label.setText(self.format_sensor_value(s9))
    def show_result(self, result):
        if "sensor_8" in result:
            r = result["sensor_8"]
            self.s8_avg_label.setText(f"{r['avg']:.4f}")
            self.s8_min_label.setText(f"{r['min']:.4f}")
            self.s8_max_label.setText(f"{r['max']:.4f}")
            self.s8_range_label.setText(f"{r['range']:.4f}")
            self.s8_std_label.setText(f"{r['std']:.4f}")
        if "sensor_9" in result:
            r = result["sensor_9"]
            self.s9_avg_label.setText(f"{r['avg']:.4f}")
            self.s9_min_label.setText(f"{r['min']:.4f}")
            self.s9_max_label.setText(f"{r['max']:.4f}")
            self.s9_range_label.setText(f"{r['range']:.4f}")
            self.s9_std_label.setText(f"{r['std']:.4f}")
    def format_sensor_value(self, value):
        if value is None or str(value).strip() in ["", "-", "None"]:
            return "---"
        try:
            return f"{float(value):.3f}"
        except ValueError:
            return "---"
    # =========================================================
    # Save CSV
    # =========================================================
    def save_result_to_csv(self, result):
        os.makedirs(self.log_dir, exist_ok=True)
        log_path = os.path.join(self.log_dir, self.log_filename)
        file_exists = os.path.isfile(log_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, mode="a", newline="") as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow([
                    "datetime",
                    "sensor",
                    "count",
                    "avg",
                    "min",
                    "max",
                    "range",
                    "std",
                ])
            for sensor_key, r in result.items():
                writer.writerow([
                    now,
                    sensor_key,
                    r["count"],
                    f"{r['avg']:.6f}",
                    f"{r['min']:.6f}",
                    f"{r['max']:.6f}",
                    f"{r['range']:.6f}",
                    f"{r['std']:.6f}",
                ])
    # =========================================================
    # Replace this with real sensor reading
    # =========================================================

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = RepeatabilityTestWindow()
    window.show()
    sys.exit(app.exec())