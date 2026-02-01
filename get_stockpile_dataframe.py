import requests
import pandas as pd
import os
from tabulate import tabulate

def get_stockpile_df(image_relative_path, label, stockpile="Public", version="airborne-63"):
    url = "http://192.168.50.44:5000/process"
    payload = {
        "image": image_relative_path,
        "label": label,
        "stockpile": stockpile,
        "version": version
    }

    print(f"Sending {image_relative_path} to Docker...")
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        tsv_local_path = result['tsv_path'] # e.g. 'sample_output/tine_report.tsv'
        
        if os.path.exists(tsv_local_path):
            # Read into Pandas
            df = pd.read_csv(tsv_local_path, sep='\t')
            print(f"Successfully created DataFrame with {len(df)} rows.")
            return df
        else:
            print("Error: TSV file was created in Docker but is missing in host volume.")
    else:
        print(f"Error from Docker: {response.text}")
    return None

# Usage Example:
if __name__ == "__main__":
    my_df = get_stockpile_df("sample_pictures/tine.png", "Tine")
    if my_df is not None:
        print(tabulate(my_df.head(), headers='keys', tablefmt='psql'))
