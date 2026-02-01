from abc import ABC, abstractmethod

class OCRResult(dict):
    """
    Standardized OCR output.
    This should match what FIR already expects downstream.
    """
    pass

class OCRBackend(ABC):
    @abstractmethod
    def run(self, image_path: str) -> OCRResult:
        pass
