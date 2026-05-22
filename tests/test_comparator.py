"""
Basic tests for the PDFComparator module
Run with: pytest tests/
"""

import pytest
from PIL import Image
import tempfile
import os

from pdf_compare import PDFComparator, PDFRenderer, PDFDiffer
from pdf_compare.stats import DiffStats, PageStats, StatsCalculator


class TestPDFRenderer:
    """Tests for PDFRenderer"""

    def test_renderer_initialization(self):
        """Test renderer can be initialized"""
        renderer = PDFRenderer(dpi=150)
        assert renderer.dpi == 150
        assert renderer.zoom == 150 / 72

    def test_normalize_images_same_size(self):
        """Test normalizing images of the same size"""
        renderer = PDFRenderer()
        img1 = Image.new('RGB', (100, 100), color='white')
        img2 = Image.new('RGB', (100, 100), color='white')

        norm_img1, norm_img2 = renderer.normalize_images(img1, img2)

        assert norm_img1.size == (100, 100)
        assert norm_img2.size == (100, 100)

    def test_normalize_images_different_sizes(self):
        """Test normalizing images of different sizes"""
        renderer = PDFRenderer()
        img1 = Image.new('RGB', (100, 100), color='white')
        img2 = Image.new('RGB', (150, 200), color='white')

        norm_img1, norm_img2 = renderer.normalize_images(img1, img2)

        # Both should be resized to the larger dimensions
        assert norm_img1.size == (150, 200)
        assert norm_img2.size == (150, 200)


class TestPDFDiffer:
    """Tests for PDFDiffer"""

    def test_differ_initialization(self):
        """Test differ can be initialized"""
        differ = PDFDiffer(threshold=10)
        assert differ.threshold == 10

    def test_compare_identical_images(self):
        """Test comparing identical images"""
        differ = PDFDiffer()
        img1 = Image.new('RGB', (100, 100), color='white')
        img2 = Image.new('RGB', (100, 100), color='white')

        are_identical, diff_img, diff_pixels = differ.compare_images(img1, img2)

        assert are_identical is True
        assert diff_pixels == 0
        assert diff_img.size == img1.size

    def test_compare_different_images(self):
        """Test comparing different images"""
        differ = PDFDiffer()
        img1 = Image.new('RGB', (100, 100), color='white')
        img2 = Image.new('RGB', (100, 100), color='black')

        are_identical, diff_img, diff_pixels = differ.compare_images(img1, img2)

        assert are_identical is False
        assert diff_pixels > 0
        assert diff_img.size == img1.size

    def test_compare_with_threshold(self):
        """Test comparing images with threshold"""
        differ = PDFDiffer(threshold=50)

        # Create images with small difference
        img1 = Image.new('RGB', (100, 100), color=(200, 200, 200))
        img2 = Image.new('RGB', (100, 100), color=(210, 210, 210))

        are_identical, diff_img, diff_pixels = differ.compare_images(img1, img2)

        # With threshold=50, these should be considered identical
        assert are_identical is True

    def test_calculate_similarity_identical(self):
        """Test similarity calculation for identical images"""
        differ = PDFDiffer()
        img1 = Image.new('RGB', (100, 100), color='white')
        img2 = Image.new('RGB', (100, 100), color='white')

        similarity = differ.calculate_similarity_percentage(img1, img2)

        assert similarity == 100.0

    def test_calculate_similarity_different(self):
        """Test similarity calculation for different images"""
        differ = PDFDiffer()
        img1 = Image.new('RGB', (100, 100), color='white')
        img2 = Image.new('RGB', (100, 100), color='black')

        similarity = differ.calculate_similarity_percentage(img1, img2)

        # Two fully-different images must report 0% similarity (regression test:
        # the denominator used to be width*height*3, capping difference at ~33%).
        assert similarity == 0.0

    def test_diff_pixels_count_matches_pixel_count(self):
        """diff_pixels must be counted per pixel, not per RGB channel"""
        differ = PDFDiffer()
        img1 = Image.new('RGB', (100, 100), color='white')
        img2 = Image.new('RGB', (100, 100), color='black')

        _, _, diff_pixels = differ.compare_images(img1, img2)

        assert diff_pixels == 100 * 100

    def test_analyze_single_pass(self):
        """analyze() returns verdict, diff image, pixel count and regions"""
        differ = PDFDiffer()
        img1 = Image.new('RGB', (100, 100), color='white')
        img2 = Image.new('RGB', (100, 100), color='black')

        is_identical, diff_img, diff_pixels, regions = differ.analyze(img1, img2)

        assert is_identical is False
        assert diff_pixels == 100 * 100
        assert diff_img.size == (100, 100)
        assert len(regions) >= 1

    def test_analyze_skips_regions_when_disabled(self):
        """analyze(detect_regions=False) must not compute regions"""
        differ = PDFDiffer()
        img1 = Image.new('RGB', (100, 100), color='white')
        img2 = Image.new('RGB', (100, 100), color='black')

        _, _, _, regions = differ.analyze(img1, img2, detect_regions=False)

        assert regions == []

    def test_find_difference_regions_locates_box(self):
        """A single rectangular difference should yield one bounding box"""
        differ = PDFDiffer()
        img1 = Image.new('RGB', (200, 200), color='white')
        img2 = Image.new('RGB', (200, 200), color='white')
        # Draw a black rectangle from (50,60) to (110,140) on the second image
        for x in range(50, 110):
            for y in range(60, 140):
                img2.putpixel((x, y), (0, 0, 0))

        regions = differ.find_difference_regions(img1, img2)

        assert len(regions) == 1
        bbox = regions[0]
        assert bbox.x1 == 50 and bbox.y1 == 60
        assert bbox.x2 == 110 and bbox.y2 == 140


class TestStatsCalculator:
    """Tests for StatsCalculator"""

    def test_calculate_page_stats_identical(self):
        """Test calculating stats for identical pages"""
        stats = StatsCalculator.calculate_page_stats(
            page_number=0,
            is_identical=True,
            total_pixels=10000,
            different_pixels=0,
            difference_regions=[]
        )

        assert stats.page_number == 0
        assert stats.is_identical is True
        assert stats.similarity_percentage == 100.0
        assert stats.difference_percentage == 0.0
        assert stats.num_difference_regions == 0

    def test_calculate_page_stats_different(self):
        """Test calculating stats for different pages"""
        stats = StatsCalculator.calculate_page_stats(
            page_number=1,
            is_identical=False,
            total_pixels=10000,
            different_pixels=1000,
            difference_regions=[]
        )

        assert stats.page_number == 1
        assert stats.is_identical is False
        assert stats.similarity_percentage == 90.0
        assert stats.difference_percentage == 10.0


class TestDiffStats:
    """Tests for DiffStats"""

    def test_diff_stats_identical(self):
        """Test DiffStats for identical PDFs"""
        page_stats = [
            PageStats(0, True, 10000, 0, 0.0, 100.0, 0, []),
            PageStats(1, True, 10000, 0, 0.0, 100.0, 0, []),
        ]

        stats = StatsCalculator.calculate_overall_stats(
            pdf1_path="test1.pdf",
            pdf2_path="test2.pdf",
            pdf1_pages=2,
            pdf2_pages=2,
            page_stats_list=page_stats
        )

        assert stats.are_identical is True
        assert stats.overall_similarity == 100.0
        assert stats.identical_pages == 2
        assert stats.different_pages == 0

    def test_diff_stats_different(self):
        """Test DiffStats for different PDFs"""
        page_stats = [
            PageStats(0, True, 10000, 0, 0.0, 100.0, 0, []),
            PageStats(1, False, 10000, 1000, 10.0, 90.0, 2, []),
        ]

        stats = StatsCalculator.calculate_overall_stats(
            pdf1_path="test1.pdf",
            pdf2_path="test2.pdf",
            pdf1_pages=2,
            pdf2_pages=2,
            page_stats_list=page_stats
        )

        assert stats.are_identical is False
        assert stats.overall_similarity == 95.0
        assert stats.identical_pages == 1
        assert stats.different_pages == 1

    def test_diff_stats_to_json(self):
        """Test converting DiffStats to JSON"""
        page_stats = [
            PageStats(0, True, 10000, 0, 0.0, 100.0, 0, []),
        ]

        stats = StatsCalculator.calculate_overall_stats(
            pdf1_path="test1.pdf",
            pdf2_path="test2.pdf",
            pdf1_pages=1,
            pdf2_pages=1,
            page_stats_list=page_stats
        )

        json_str = stats.to_json()

        assert isinstance(json_str, str)
        assert "test1.pdf" in json_str
        assert "test2.pdf" in json_str


class TestPDFComparator:
    """Tests for PDFComparator"""

    def test_comparator_initialization(self):
        """Test comparator can be initialized"""
        comparator = PDFComparator(dpi=200, threshold=10)
        assert comparator.renderer.dpi == 200
        assert comparator.differ.threshold == 10

    def test_get_exit_code_no_comparison(self):
        """Test exit code when no comparison has been done"""
        comparator = PDFComparator()
        exit_code = comparator.get_exit_code()
        assert exit_code == 1

    def test_compare_nonexistent_file(self):
        """Test comparing non-existent files raises error"""
        comparator = PDFComparator()

        with pytest.raises(FileNotFoundError):
            comparator.compare("nonexistent1.pdf", "nonexistent2.pdf")

    def test_save_without_comparison(self):
        """Test saving outputs without comparison raises error"""
        comparator = PDFComparator()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "output.pdf")

            with pytest.raises(RuntimeError):
                comparator.save_diff_pdf(output_path)


class TestEndToEnd:
    """End-to-end tests on real PDFs (render -> diff -> stats pipeline)"""

    @staticmethod
    def _make_pdf(path, pages_text):
        fitz = pytest.importorskip("fitz")
        doc = fitz.open()
        for text in pages_text:
            page = doc.new_page()
            page.insert_text((72, 72), text, fontsize=24)
        doc.save(path)
        doc.close()

    def test_identical_pdfs(self):
        """Identical PDFs compare as identical with 100% similarity"""
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "a.pdf")
            p2 = os.path.join(tmpdir, "b.pdf")
            self._make_pdf(p1, ["Hello world", "Second page"])
            self._make_pdf(p2, ["Hello world", "Second page"])

            comparator = PDFComparator(dpi=72)
            stats = comparator.compare(p1, p2)

            assert stats.are_identical is True
            assert stats.overall_similarity == 100.0
            assert comparator.get_exit_code() == 0

    def test_different_pdfs(self):
        """PDFs with different content compare as different"""
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "a.pdf")
            p2 = os.path.join(tmpdir, "b.pdf")
            self._make_pdf(p1, ["Hello world"])
            self._make_pdf(p2, ["Completely different text here"])

            comparator = PDFComparator(dpi=72)
            stats = comparator.compare(p1, p2)

            assert stats.are_identical is False
            assert stats.different_pages == 1
            assert stats.page_stats[0].similarity_percentage < 100.0
            assert comparator.get_exit_code() == 1

    def test_different_page_counts(self):
        """PDFs with different page counts are never identical"""
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "a.pdf")
            p2 = os.path.join(tmpdir, "b.pdf")
            self._make_pdf(p1, ["Page one", "Page two"])
            self._make_pdf(p2, ["Page one"])

            comparator = PDFComparator(dpi=72)
            stats = comparator.compare(p1, p2)

            assert stats.pdf1_pages == 2
            assert stats.pdf2_pages == 1
            assert stats.pages_compared == 1
            assert stats.are_identical is False

    def test_compare_without_regions(self):
        """Comparison with detect_regions=False still yields a verdict"""
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "a.pdf")
            p2 = os.path.join(tmpdir, "b.pdf")
            self._make_pdf(p1, ["Hello"])
            self._make_pdf(p2, ["World"])

            comparator = PDFComparator(dpi=72)
            stats = comparator.compare(p1, p2, detect_regions=False)

            assert stats.are_identical is False
            assert stats.page_stats[0].num_difference_regions == 0


# Run tests with: pytest tests/test_comparator.py -v
