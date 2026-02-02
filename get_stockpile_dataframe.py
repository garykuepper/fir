import requests
import pandas as pd
import io

def get_stockpile_df_from_server(server_ip, image_path, label, stockpile="Public", version="airborne-63"):
    url = f"http://{server_ip}:5000/process"
    
    # Payload for form data
    data = {
        "label": label,
        "stockpile": stockpile,
        "version": version
    }
    
    # Attach the physical file
    files = {
        'image': open(image_path, 'rb')
    }

    print(f"Uploading {image_path} to {server_ip}...")
    try:
        response = requests.post(url, data=data, files=files, timeout=180)
        response.raise_for_status()
        
        # Convert the received TSV bytes directly into a DataFrame
        df = pd.read_csv(io.StringIO(response.text), sep='\t')
        print(f"Successfully received data: {len(df)} rows.")
        return df

    except Exception as e:
        print(f"Error processing image: {e}")
        return None

if __name__ == "__main__":
    # Example: Running from a different machine
    # Replace with your Ubuntu server IP
    SERVER_IP = "192.168.50.44"
    
    df = get_stockpile_df_from_server(SERVER_IP, "sample_pictures/tine.png", "Remote_Tine_Report")
    if df is not None:
        print(df.head())
