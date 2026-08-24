from pathlib import Path
import unittest


REPORT_SOURCE = Path(__file__).resolve().parents[2] / "report" / "internship_main.tex"
VIETNAMESE_REPORT_SOURCE = (
    Path(__file__).resolve().parents[2] / "report" / "internship_main_vi.tex"
)


class InternshipReportSourceTests(unittest.TestCase):
    def test_final_review_source_has_no_internal_status_page(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")

        self.assertNotIn("Report Status and Required Company Confirmation", source)
        self.assertNotIn("signed colour scan still required", source)

    def test_final_review_source_has_one_company_confirmation_block(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")

        self.assertEqual(1, source.count("AUTHORISED COMPANY REPRESENTATIVE"))
        self.assertNotIn("ENTERPRISE SUPERVISOR}\\\\[0.1cm]", source)

    def test_source_uses_confirmed_enterprise_mentor(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")

        self.assertIn("Vo Tan Phat (VNPT-IT)", source)
        self.assertNotIn("[TO BE CONFIRMED BY THE COMPANY]", source)

    def test_vietnamese_comparison_source_is_clearly_non_submission(self) -> None:
        source = VIETNAMESE_REPORT_SOURCE.read_text(encoding="utf-8")

        self.assertIn("BẢN ĐỐI CHIẾU -- KHÔNG NỘP CHÍNH THỨC", source)
        self.assertIn("Võ Tấn Phát (VNPT-IT)", source)
        self.assertIn("BÁO CÁO MÔN HỌC THỰC TẬP NGOÀI TRƯỜNG", source)


if __name__ == "__main__":
    unittest.main()
