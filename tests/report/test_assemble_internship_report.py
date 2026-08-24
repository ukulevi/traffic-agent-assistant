from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pypdf import PdfReader, PdfWriter

from scripts.report.assemble_internship_report import assemble_report


def _write_blank_pdf(path: Path, pages: int) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with path.open("wb") as stream:
        writer.write(stream)


class AssembleInternshipReportTests(unittest.TestCase):
    def test_requires_d2_for_submission_package(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            main = root / "main.pdf"
            _write_blank_pdf(main, 2)

            with self.assertRaisesRegex(ValueError, "D2 PDF is required"):
                assemble_report(main_pdf_path=main, output_pdf_path=root / "out.pdf")

    def test_places_d2_after_cover_and_keeps_remaining_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            main = root / "main.pdf"
            d2 = root / "d2.pdf"
            output = root / "out.pdf"
            _write_blank_pdf(main, 3)
            _write_blank_pdf(d2, 2)

            assemble_report(
                main_pdf_path=main,
                d2_pdf_path=d2,
                output_pdf_path=output,
            )

            self.assertEqual(5, len(PdfReader(output).pages))


if __name__ == "__main__":
    unittest.main()
