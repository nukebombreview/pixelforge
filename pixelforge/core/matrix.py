"""
PixelForge — PixelMatrix
NumPy-backed 2D pixel buffer for rendering and output.
"""

import numpy as np


class PixelMatrix:
    """A 2D pixel buffer backed by a NumPy array.

    The internal buffer is an ``(height, width, 3)`` ``uint8`` array
    representing RGB pixel data.  All rendering, blending, and protocol
    output operations ultimately read from or write to this buffer.
    """

    def __init__(self, width: int = 32, height: int = 32):
        self.width = width
        self.height = height
        self._buffer: np.ndarray = np.zeros((height, width, 3), dtype=np.uint8)

    # ------------------------------------------------------------------
    # Basic pixel operations
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Set every pixel to black ``(0, 0, 0)``."""
        self._buffer[:] = 0

    def fill(self, r: int, g: int, b: int) -> None:
        """Fill the entire matrix with a single solid colour."""
        self._buffer[:, :, 0] = r
        self._buffer[:, :, 1] = g
        self._buffer[:, :, 2] = b

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self._buffer[y, x] = (r, g, b)

    def get_pixel(self, x: int, y: int) -> tuple[int, int, int]:
        if 0 <= x < self.width and 0 <= y < self.height:
            px = self._buffer[y, x]
            return int(px[0]), int(px[1]), int(px[2])
        return (0, 0, 0)

    # ------------------------------------------------------------------
    # Buffer access
    # ------------------------------------------------------------------

    @property
    def buffer(self) -> np.ndarray:
        """Raw ``uint8`` buffer — shape ``(H, W, 3)``."""
        return self._buffer

    @buffer.setter
    def buffer(self, data: np.ndarray) -> None:
        self._buffer = np.clip(data, 0, 255).astype(np.uint8)

    def get_float_buffer(self) -> np.ndarray:
        """Return the buffer as ``float64`` in the range ``[0.0, 1.0]``."""
        return self._buffer.astype(np.float64) / 255.0

    def set_from_float(self, data: np.ndarray) -> None:
        """Set the buffer from a ``float64`` array in ``[0.0, 1.0]``."""
        self._buffer = np.clip(data * 255.0, 0, 255).astype(np.uint8)

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def resize(self, width: int, height: int) -> None:
        """Resize the matrix (clears all data)."""
        self.width = width
        self.height = height
        self._buffer = np.zeros((height, width, 3), dtype=np.uint8)

    def copy(self) -> "PixelMatrix":
        """Return a deep copy."""
        m = PixelMatrix(self.width, self.height)
        m._buffer = self._buffer.copy()
        return m

    # ------------------------------------------------------------------
    # Blending
    # ------------------------------------------------------------------

    def blend(self, other: "PixelMatrix", factor: float) -> "PixelMatrix":
        """Linear interpolation: ``(1 - factor) * self + factor * other``.

        *factor* is clamped to ``[0.0, 1.0]``.  Returns a **new** matrix.
        """
        result = PixelMatrix(self.width, self.height)
        f = float(np.clip(factor, 0.0, 1.0))
        blended = (
            (1.0 - f) * self._buffer.astype(np.float64)
            + f * other._buffer.astype(np.float64)
        )
        result._buffer = np.clip(blended, 0, 255).astype(np.uint8)
        return result

    def apply_master_dimmer(self, dimmer: float) -> "PixelMatrix":
        """Return a new matrix with global dimmer applied (0.0 – 1.0)."""
        result = PixelMatrix(self.width, self.height)
        d = float(np.clip(dimmer, 0.0, 1.0))
        result._buffer = (self._buffer.astype(np.float64) * d).astype(np.uint8)
        return result

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_qimage(self):
        """Convert to a ``QImage`` suitable for display in a ``QLabel``."""
        from PyQt6.QtGui import QImage

        h, w, _ = self._buffer.shape
        bytes_per_line = 3 * w
        # .copy() is essential — QImage does not own the numpy data.
        return QImage(
            self._buffer.data, w, h, bytes_per_line,
            QImage.Format.Format_RGB888,
        ).copy()

    def to_dmx_bytes(self, channel_order: str = "RGB") -> bytes:
        """Flatten the matrix to a byte string for DMX / Art-Net output.

        Pixels are serialised row-by-row, left-to-right.  ``channel_order``
        may be ``"RGB"``, ``"GRB"``, ``"BGR"``, ``"RGBW"`` etc.
        """
        flat = self._buffer.reshape(-1, 3)
        order_map = {"R": 0, "G": 1, "B": 2}
        indices = [order_map.get(ch, 0) for ch in channel_order.upper() if ch in order_map]
        if not indices:
            indices = [0, 1, 2]
        reordered = flat[:, indices]
        return reordered.tobytes()

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

    def __repr__(self) -> str:
        return f"PixelMatrix({self.width}×{self.height})"
