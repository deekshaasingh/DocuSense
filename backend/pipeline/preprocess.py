"""
Step 3 of the Build Manual: turn any input into a clean, straight image.

pdf_to_images: PDF -> per-page numpy arrays via PyMuPDF, 200 DPI.
deskew: projection-profile / sharpness-search method. Deliberately NOT
cv2.minAreaRect on ink pixels -- that trick is unreliable on real pages
because which edge OpenCV calls "width" flips unpredictably. This version
was tested against synthetic skews of -7, -2.5, 0, +3.5, +8 degrees and
recovered every one to within 0.5 degrees (see backend/tests/test_preprocess.py).
"""
import pymupdf
import cv2
import numpy as np

from config import settings


def pdf_to_images(path: str, dpi: int = 200, max_pages: int | None = None):
    doc = pymupdf.open(path)
    limit = max_pages if max_pages is not None else settings.MAX_PAGES
    for i, page in enumerate(doc):
        if i >= limit:
            break
        pix = page.get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif pix.n == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        yield img


def deskew(img: np.ndarray, limit: float = 10.0, step: float = 0.5) -> np.ndarray:
    """Try a range of angles, keep the one where the text lines up best."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    h, w = mask.shape

    def sharpness(angle: float) -> float:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        rot = cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_NEAREST)
        rows = rot.sum(axis=1, dtype=np.float64)  # how much ink is in each row
        return float((np.diff(rows) ** 2).sum())  # sharp jumps = straight text lines

    best = max(np.arange(-limit, limit + step, step), key=sharpness)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), best, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def denoise_and_contrast(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(denoised)


def clean(img: np.ndarray) -> np.ndarray:
    """Full Step-3 pipeline: grayscale -> deskew -> denoise/contrast."""
    straightened = deskew(img)
    return denoise_and_contrast(straightened)


def preprocess_file(path: str, dpi: int = 200) -> list[np.ndarray]:
    """PDF or image path in, list of cleaned page arrays out.

    Multi-page PDFs come back as one cleaned array per page, capped at
    settings.MAX_PAGES. The manual (Section 11) is explicit that pages are
    processed one at a time and merged afterwards rather than sent to the
    model together; pipeline/extract.py::extract_pages does the merging.
    """
    if path.lower().endswith(".pdf"):
        pages = list(pdf_to_images(path, dpi=dpi))
    else:
        img = cv2.imread(path)
        if img is None:
            raise ValueError(f"Could not read image: {path}")
        pages = [img]
    if not pages:
        raise ValueError(f"No pages found in: {path}")
    return [clean(p) for p in pages]
