import pandas as pd
import os

folder = r"D:\Displacement\Log"

csv_files = [f for f in os.listdir(folder) if f.endswith(".csv")]

combind_df = pd.concat(
    [pd.read_csv(os.path.join(folder, f)) for f in csv_files], 
    ignore_index=True
)

combind_df.to_csv("Merge_log.csv", index=False)