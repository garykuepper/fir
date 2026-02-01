# ocr/__init__.py
import os
from .browser_ocr import BrowserOCR
from .gpu_ocr import GPUOCR

def get_ocr_backend():
    mode = os.getenv("FIR_OCR_BACKEND", "browser").lower()

    if mode == "gpu":
        return GPUOCR()
    else:
        return BrowserOCR()
