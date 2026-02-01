import subprocess
import os
import uuid
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Directory for temporary processing
UPLOAD_FOLDER = '/tmp/fir_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('sample_output', exist_ok=True)

# Start the FIR Website server in the background
subprocess.Popen(["python3", "-m", "http.server", "8005"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@app.route('/process', methods=['POST'])
def process_image():
    # 1. Get parameters and the uploaded file
    label = request.form.get("label", "Default_Label")
    stockpile = request.form.get("stockpile", "Public")
    version = request.form.get("version", "airborne-63")
    
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400
    
    file = request.files['image']
    # Create a unique filename to prevent collisions between different users
    unique_id = str(uuid.uuid4())[:8]
    temp_image_path = os.path.join(UPLOAD_FOLDER, f"{unique_id}_{secure_filename(file.filename)}")
    file.save(temp_image_path)

    try:
        # 2. Run the Node.js automation
        # We pass the temp_image_path directly to the script
        node_cmd = ["node", "headless_process.js", temp_image_path, label, stockpile, version]
        subprocess.run(node_cmd, check=True)
        
        # 3. Locate the generated TSV
        safe_name = "".join([c if c.isalnum() else "_" for c in label]).lower()
        tsv_path = os.path.join("sample_output", f"{safe_name}_report.tsv")
        
        # 4. Return the file back to the user
        return send_file(tsv_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Cleanup the uploaded image
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
