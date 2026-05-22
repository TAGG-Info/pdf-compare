"""
PDF Renderer module - Converts PDF pages to images using PyMuPDF
"""

import fitz  # PyMuPDF
from PIL import Image
from typing import List, Tuple
from contextlib import contextmanager


class PDFRenderer:
    """Handles PDF rendering to images for comparison"""

    def __init__(self, dpi: int = 150):
        """
        Initialize the PDF renderer

        Args:
            dpi: Resolution for rendering (default: 150, higher = better quality but slower)
        """
        self.dpi = dpi
        self.zoom = dpi / 72  # 72 is the default DPI for PDF

    @contextmanager
    def open_document(self, pdf_path: str):
        """
        Context manager for opening PDF documents.

        Open a PDF once and render several pages from the yielded document to
        avoid the cost of re-parsing the file for every page.

        Args:
            pdf_path: Path to the PDF file

        Yields:
            fitz.Document: Opened PDF document

        Example:
            with renderer.open_document("file.pdf") as doc:
                img = renderer.render_page_from_doc(doc, 0)
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            yield doc
        except Exception as e:
            raise RuntimeError(f"Failed to open PDF '{pdf_path}': {str(e)}")
        finally:
            if doc is not None:
                doc.close()

    # Backwards-compatible private alias.
    _open_pdf = open_document

    def render_page_from_doc(self, doc, page_num: int) -> Image.Image:
        """
        Render a single page from an already-open PyMuPDF document.

        Args:
            doc: An open ``fitz.Document``
            page_num: Page number (0-indexed)

        Returns:
            PIL Image object of the rendered page
        """
        if page_num >= doc.page_count:
            raise ValueError(
                f"Page {page_num} does not exist (total: {doc.page_count})"
            )

        page = doc[page_num]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        # Convert pixmap to PIL Image directly (faster than PNG encoding)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    def get_page_count(self, pdf_path: str) -> int:
        """
        Get the number of pages in a PDF

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Number of pages in the PDF
        """
        with self.open_document(pdf_path) as doc:
            return doc.page_count

    def render_page(self, pdf_path: str, page_num: int) -> Image.Image:
        """
        Render a single PDF page to a PIL Image

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (0-indexed)

        Returns:
            PIL Image object of the rendered page
        """
        try:
            with self.open_document(pdf_path) as doc:
                return self.render_page_from_doc(doc, page_num)
        except Exception as e:
            raise RuntimeError(f"Failed to render page {page_num} from '{pdf_path}': {str(e)}")

    def render_all_pages(self, pdf_path: str) -> List[Image.Image]:
        """
        Render all pages from a PDF to a list of PIL Images

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of PIL Image objects, one per page
        """
        try:
            with self.open_document(pdf_path) as doc:
                return [
                    self.render_page_from_doc(doc, page_num)
                    for page_num in range(doc.page_count)
                ]
        except Exception as e:
            raise RuntimeError(f"Failed to render pages from '{pdf_path}': {str(e)}")

    def get_page_dimensions(self, pdf_path: str, page_num: int = 0) -> Tuple[int, int]:
        """
        Get the dimensions of a rendered page

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (0-indexed, default: 0)

        Returns:
            Tuple of (width, height) in pixels
        """
        try:
            with self.open_document(pdf_path) as doc:
                page = doc[page_num]
                rect = page.rect

                # Apply zoom factor
                width = int(rect.width * self.zoom)
                height = int(rect.height * self.zoom)

                return (width, height)

        except Exception as e:
            raise RuntimeError(f"Failed to get dimensions from '{pdf_path}': {str(e)}")

    def normalize_images(self, img1: Image.Image, img2: Image.Image) -> Tuple[Image.Image, Image.Image]:
        """
        Normalize two images to have the same dimensions
        Pads the smaller image with white background

        Args:
            img1: First image
            img2: Second image

        Returns:
            Tuple of normalized images with same dimensions
        """
        width = max(img1.width, img2.width)
        height = max(img1.height, img2.height)

        if img1.size != (width, height):
            new_img1 = Image.new('RGB', (width, height), 'white')
            new_img1.paste(img1, (0, 0))
            img1 = new_img1

        if img2.size != (width, height):
            new_img2 = Image.new('RGB', (width, height), 'white')
            new_img2.paste(img2, (0, 0))
            img2 = new_img2

        return img1, img2
