import subprocess
import time
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# Start the FIR Website server globally so it's always ready in the background
print("--> Starting FIR Website Server on port 8005...")
server_process = subprocess.Popen(
    ["python3", "-m", "http.server", "8005"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

@app.route('/process', methods=['POST'])
def process_image():
    data = request.json
    image_path = data.get("image")
    label = data.get("label", "Default_Label")
    stockpile = data.get("stockpile", "Public")
    version = data.get("version", "airborne-63")

    if not image_path or not os.path.exists(image_path):
        return jsonify({"error": f"Image not found at path: {image_path}"}), 400

    print(f"--> Received Request: {image_path} | Label: {label}")
    
    # Run the Node.js Playwright script
    node_cmd = ["node", "headless_process.js", image_path, label, stockpile, version]
    
    try:
        # Run OCR automation
        subprocess.run(node_cmd, check=True)
        
        # Determine the generated filename based on headless_process.js logic
        safe_name = "".join([c if c.isalnum() else "_" for c in label]).lower()
        tsv_filename = f"{safe_name}_report.tsv"
        tsv_path = os.path.join("sample_output", tsv_filename)
        
        return jsonify({
            "status": "success",
            "tsv_path": tsv_path,
            "filename": tsv_filename
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    try:
        # Flask API listens on 5000
        print("--> FIR API Service Ready on port 5000")
        app.run(host='0.0.0.0', port=5000)
    finally:
        print("--> Cleaning up server...")
        server_process.terminate()
