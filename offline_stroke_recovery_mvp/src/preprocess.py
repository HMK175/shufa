import numpy as np


def ensure_foreground_is_true(image: np.ndarray, threshold: int = 200) -> np.ndarray:
    arr = np.asarray(image)
    return arr < threshold


def crop_to_foreground(mask: np.ndarray, pad: int = 2):
    ys, xs = np.nonzero(mask)
    y0 = max(int(ys.min()) - pad, 0)
    y1 = min(int(ys.max()) + pad + 1, mask.shape[0])
    x0 = max(int(xs.min()) - pad, 0)
    x1 = min(int(xs.max()) + pad + 1, mask.shape[1])
    return mask[y0:y1, x0:x1], (y0, x0, y1 - 1, x1 - 1)
