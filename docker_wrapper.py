import os
import subprocess
import uuid
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

from gpu_ocr_client import gpu_ocr_lines

app = Flask(__name__)

# ------------------------------------------------------------------------------
# Directories
# ------------------------------------------------------------------------------
UPLOAD_FOLDER = Path("/tmp/fir_uploads")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = Path("/app/sample_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------------------
# Start the FIR Website server in the background (serves /app contents on 8005)
# ------------------------------------------------------------------------------
subprocess.Popen(
    ["python3", "-m", "http.server", "8005"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def get_free_vram_mb() -> int | None:
    """
    Returns free VRAM in MiB for GPU 0, or None if nvidia-smi isn't available.
    """
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            text=True,
        ).strip()
        return int(out.splitlines()[0])
    except Exception:
        return None


def write_simple_tsv(tsv_path: Path, lines: list[str]) -> None:
    """
    Write a simple 1-column TSV so the API contract stays the same
    (client still downloads a .tsv file).
    """
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    with tsv_path.open("w", encoding="utf-8") as f:
        f.write("text\n")
        for line in lines:
            safe = (line or "").replace("\t", " ").replace("\r", " ").replace("\n", " ")
            f.write(f"{safe}\n")


# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.route("/process", methods=["POST"])
def process_image():
    label = request.form.get("label", "Default_Label")
    stockpile = request.form.get("stockpile", "Public")
    version = request.form.get("version", "airborne-63")

    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]

    unique_id = str(uuid.uuid4())[:8]
    temp_image_path = UPLOAD_FOLDER / f"{unique_id}_{secure_filename(file.filename)}"
    file.save(temp_image_path)

    safe_name = "".join(c if c.isalnum() else "_" for c in label).lower()
    tsv_path = OUTPUT_DIR / f"{safe_name}_report.tsv"

    try:
        # ----------------------------------------------------------------------
        # Decide backend
        # ----------------------------------------------------------------------
        backend = os.getenv("FIR_OCR_BACKEND", "browser").lower()

        free_mb = get_free_vram_mb()
        vram_threshold_mb = int(os.getenv("FIR_VRAM_THRESHOLD_MB", "1000"))

        # ----------------------------------------------------------------------
        # GPU SIDECAR PATH (preferred)
        # ----------------------------------------------------------------------
        if backend == "gpu":
            if free_mb is not None and free_mb < vram_threshold_mb:
                print(
                    f"[INFO] GPU requested but free VRAM is low "
                    f"({free_mb} MiB < {vram_threshold_mb} MiB). "
                    "Falling back to browser OCR."
                )
            else:
                try:
                    lines = gpu_ocr_lines(str(temp_image_path))
                    write_simple_tsv(tsv_path, lines)
                    return send_file(tsv_path, as_attachment=True)
                except Exception as e:
                    print(f"[WARN] GPU OCR failed, falling back to browser OCR: {e}")

        # ----------------------------------------------------------------------
        # LEGACY BROWSER (Playwright) PATH
        # ----------------------------------------------------------------------
        node_cmd = [
            "node",
            "headless_process.js",
            str(temp_image_path),
            label,
            stockpile,
            version,
        ]

        env = os.environ.copy()
        env.setdefault("FIR_GPU_MODE", "gpu")

        # If VRAM is low, tell Node side to avoid GPU paths
        if free_mb is not None and free_mb < vram_threshold_mb:
            env["FIR_GPU_MODE"] = "cpu"

        result = subprocess.run(
            node_cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=int(os.getenv("FIR_NODE_TIMEOUT_SEC", "180")),
        )

        if result.returncode != 0:
            return jsonify({
                "error": "headless_process failed",
                "backend": "browser",
                "gpu_mode": env.get("FIR_GPU_MODE"),
                "free_vram_mb": free_mb,
                "stdout_tail": (result.stdout or "")[-2000:],
                "stderr_tail": (result.stderr or "")[-2000:],
            }), 500

        if not tsv_path.exists():
            return jsonify({
                "error": "TSV not found after processing",
                "expected_path": str(tsv_path),
                "backend": "browser",
                "gpu_mode": env.get("FIR_GPU_MODE"),
                "free_vram_mb": free_mb,
                "stdout_tail": (result.stdout or "")[-2000:],
                "stderr_tail": (result.stderr or "")[-2000:],
            }), 500

        return send_file(tsv_path, as_attachment=True)

    except subprocess.TimeoutExpired:
        return jsonify({"error": "headless_process timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if temp_image_path.exists():
                temp_image_path.unlink()
        except Exception:
            pass


# ------------------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # Keep as 0.0.0.0 inside container; control exposure via docker-compose
    app.run(host="0.0.0.0", port=5000)
