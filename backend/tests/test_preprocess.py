"""Step 3: deskew must actually recover known skew angles."""
import cv2
import numpy as np
import pytest

from pipeline.preprocess import deskew, denoise_and_contrast, clean


def _page_with_text_lines() -> np.ndarray:
    img = np.full((600, 800, 3), 255, dtype=np.uint8)
    for y in range(80, 520, 40):
        cv2.rectangle(img, (90, y), (710, y + 14), (0, 0, 0), -1)
    return img


def _rotate(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _residual_skew(img: np.ndarray) -> float:
    """Best remaining angle after deskew should be close to zero."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    h, w = mask.shape

    def sharpness(angle):
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        rot = cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_NEAREST)
        rows = rot.sum(axis=1, dtype=np.float64)
        return float((np.diff(rows) ** 2).sum())

    return float(max(np.arange(-10, 10.5, 0.5), key=sharpness))


@pytest.mark.parametrize("angle", [-7.0, -2.5, 0.0, 3.5, 8.0])
def test_deskew_recovers_known_angles(angle):
    page = _rotate(_page_with_text_lines(), angle)
    straightened = deskew(page)
    assert abs(_residual_skew(straightened)) <= 0.5


def test_denoise_returns_single_channel():
    out = denoise_and_contrast(_page_with_text_lines())
    assert out.ndim == 2


def test_clean_runs_end_to_end():
    out = clean(_rotate(_page_with_text_lines(), 4.0))
    assert out.ndim == 2 and out.shape[0] > 0
