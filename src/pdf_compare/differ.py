"""
PDF Differ module - Detects and highlights differences between images
"""

from PIL import Image, ImageChops, ImageDraw
from typing import Tuple, List
import numpy as np
from scipy import ndimage


# Minimum bounding-box area (in pixels) below which a difference region is
# treated as noise and ignored.
MIN_REGION_AREA = 10


class BoundingBox:
    """Represents a bounding box around a difference region"""

    def __init__(self, x1: int, y1: int, x2: int, y2: int):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        return self.width * self.height

    def __repr__(self) -> str:
        return f"BoundingBox(x={self.x1}, y={self.y1}, w={self.width}, h={self.height})"


class PDFDiffer:
    """Handles pixel-level comparison and difference detection"""

    def __init__(self, threshold: int = 0):
        """
        Initialize the differ

        Args:
            threshold: Pixel difference threshold (0-255). Pixels with difference
                      below this threshold are considered identical. Default: 0 (exact match)
        """
        self.threshold = threshold

    def _diff_gray_array(self, img1: Image.Image, img2: Image.Image) -> np.ndarray:
        """
        Compute the thresholded grayscale difference between two images.

        This is the single source of truth for the per-pixel difference: every
        public method derives its result from this array so the diff is only
        computed once per image pair.

        Returns:
            uint8 numpy array (height, width); non-zero entries are differing pixels.
        """
        if img1.size != img2.size:
            raise ValueError("Images must have the same dimensions for comparison")

        if img1.mode != 'RGB':
            img1 = img1.convert('RGB')
        if img2.mode != 'RGB':
            img2 = img2.convert('RGB')

        diff_gray = ImageChops.difference(img1, img2).convert('L')
        arr = np.asarray(diff_gray)

        if self.threshold > 0:
            # Zero-out pixels whose difference is within the tolerance.
            arr = np.where(arr <= self.threshold, 0, arr).astype(np.uint8)

        return arr

    @staticmethod
    def _highlight(base_img: Image.Image, diff_arr: np.ndarray) -> Image.Image:
        """Overlay differing pixels in red on a copy of ``base_img``."""
        base = base_img.convert('RGB') if base_img.mode != 'RGB' else base_img.copy()
        mask = Image.fromarray(np.where(diff_arr > 0, 255, 0).astype(np.uint8), mode='L')
        red_overlay = Image.new('RGB', base.size, (255, 0, 0))
        base.paste(red_overlay, mask=mask)
        return base

    def _find_bounding_boxes(self, diff_arr: np.ndarray) -> List[BoundingBox]:
        """
        Find bounding boxes around connected difference regions.

        Uses :func:`scipy.ndimage.label` (4-connectivity) which is vectorised in
        C, instead of a Python-level flood fill over every pixel.
        """
        mask = diff_arr > 0
        if not mask.any():
            return []

        labeled, num_features = ndimage.label(mask)
        if num_features == 0:
            return []

        bboxes: List[BoundingBox] = []
        for sl in ndimage.find_objects(labeled):
            if sl is None:
                continue
            y_slice, x_slice = sl
            bbox = BoundingBox(x_slice.start, y_slice.start, x_slice.stop, y_slice.stop)
            if bbox.area > MIN_REGION_AREA:  # Ignore very small regions (noise)
                bboxes.append(bbox)

        return bboxes

    def analyze(
        self,
        img1: Image.Image,
        img2: Image.Image,
        detect_regions: bool = True,
    ) -> Tuple[bool, Image.Image, int, List[BoundingBox]]:
        """
        Compare two images in a single pass.

        Args:
            img1: First image
            img2: Second image
            detect_regions: Whether to compute difference-region bounding boxes
                            (skipped when not needed to save time)

        Returns:
            Tuple of (are_identical, diff_image, diff_pixel_count, regions)
        """
        diff_arr = self._diff_gray_array(img1, img2)
        diff_pixels = int(np.count_nonzero(diff_arr))
        are_identical = diff_pixels == 0
        diff_highlighted = self._highlight(img1, diff_arr)
        regions = self._find_bounding_boxes(diff_arr) if detect_regions else []
        return are_identical, diff_highlighted, diff_pixels, regions

    def compare_images(self, img1: Image.Image, img2: Image.Image) -> Tuple[bool, Image.Image, int]:
        """
        Compare two images and generate a diff image.

        Returns:
            Tuple of (are_identical, diff_image, diff_pixel_count)
            - are_identical: True if images are identical within threshold
            - diff_image: Image highlighting differences in red
            - diff_pixel_count: Number of pixels that differ
        """
        are_identical, diff_highlighted, diff_pixels, _ = self.analyze(
            img1, img2, detect_regions=False
        )
        return are_identical, diff_highlighted, diff_pixels

    def find_difference_regions(self, img1: Image.Image, img2: Image.Image) -> List[BoundingBox]:
        """
        Find bounding boxes around contiguous regions of differences.

        Returns:
            List of BoundingBox objects representing difference regions
        """
        diff_arr = self._diff_gray_array(img1, img2)
        return self._find_bounding_boxes(diff_arr)

    def create_annotated_diff(self, img1: Image.Image, img2: Image.Image,
                             highlight_color: Tuple[int, int, int] = (255, 0, 0),
                             box_regions: bool = True) -> Image.Image:
        """
        Create an annotated difference image with colored overlays and optional bounding boxes.

        Args:
            img1: First image
            img2: Second image
            highlight_color: RGB color for highlighting differences (default: red)
            box_regions: If True, draw bounding boxes around difference regions

        Returns:
            Annotated difference image
        """
        _, diff_img, _, regions = self.analyze(img1, img2, detect_regions=box_regions)

        if box_regions:
            draw = ImageDraw.Draw(diff_img)
            for bbox in regions:
                draw.rectangle(
                    [bbox.x1, bbox.y1, bbox.x2, bbox.y2],
                    outline=highlight_color,
                    width=3
                )

        return diff_img

    def calculate_similarity_percentage(self, img1: Image.Image, img2: Image.Image) -> float:
        """
        Calculate the percentage of similarity between two images.

        Returns:
            Similarity percentage (0.0 to 100.0)
        """
        _, _, diff_pixels = self.compare_images(img1, img2)
        total_pixels = img1.width * img1.height  # diff_pixels is counted per pixel

        if total_pixels == 0:
            return 100.0

        similarity = ((total_pixels - diff_pixels) / total_pixels) * 100
        return similarity
