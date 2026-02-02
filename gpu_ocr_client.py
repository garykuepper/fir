import os
import time
import requests

GPU_URL = os.getenv("FIR_GPU_OCR_URL", "http://fir-ocr-gpu:9000")

def gpu_ocr_lines(image_path: str, timeout_s: int = 180) -> list[str]:
    # Wait for service to come up (it may be downloading on first call)
    last_err = None
    for _ in range(30):
        try:
            requests.get(f"{GPU_URL}/health", timeout=1)
            break
        except Exception as e:
            last_err = e
            time.sleep(1)

    # Now attempt OCR (long timeout for first run)
    for _ in range(10):
        try:
            with open(image_path, "rb") as f:
                r = requests.post(
                    f"{GPU_URL}/ocr",
                    files={"image": f},
                    timeout=timeout_s,
                )
            r.raise_for_status()
            return r.json().get("lines", [])
        except Exception as e:
            last_err = e
            time.sleep(1)

    raise RuntimeError(f"GPU OCR failed: {last_err}")
