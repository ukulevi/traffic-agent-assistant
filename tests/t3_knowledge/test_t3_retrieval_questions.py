"""Retrieval test questions for Phase 3 - minimum 50 questions.

Categories:
- Answerable: terms are present in the two synthetic sample chunks.
- Unanswerable: intentionally unrelated/nonsense terms with no expected match.
- Pre-effective: valid-looking legal terms before 2025-01-01 must abstain.
"""

import unittest
from datetime import datetime

from stwi.contracts.knowledge import RetrievalQuery
from stwi.t3_knowledge.fake_retriever import (
    FakeRetriever,
    sample_law_35_chunk,
    sample_law_36_chunk,
)


# Question format: (query_text, scenario_time, expected_document_id or None)
RETRIEVAL_QUESTIONS = [
    # Answerable questions - law 35
    ("quyền nghĩa vụ người sử dụng đường", datetime(2025, 6, 1), "law-35-2024-qh15"),
    ("phương tiện giao thông", datetime(2025, 6, 1), "law-35-2024-qh15"),
    ("biển báo đường bộ", datetime(2025, 6, 1), "law-35-2024-qh15"),
    ("quan hệ pháp luật giao thông", datetime(2025, 6, 1), "law-35-2024-qh15"),
    ("nguyên tắc quản lý đường bộ", datetime(2025, 6, 1), "law-35-2024-qh15"),
    ("bến phà đường bộ", datetime(2025, 6, 1), "law-35-2024-qh15"),
    # Answerable questions - law 36
    ("trật tự giao thông", datetime(2025, 6, 1), "law-36-2024-qh15"),
    ("người lái xe", datetime(2025, 6, 1), "law-36-2024-qh15"),
    ("điều 10", datetime(2025, 6, 1), "law-36-2024-qh15"),
    ("hình sự nghiêm trọng", datetime(2025, 6, 1), "law-36-2024-qh15"),
    ("người đi bộ dẫn xe", datetime(2025, 6, 1), "law-36-2024-qh15"),
    ("tránh tai nạn", datetime(2025, 6, 1), "law-36-2024-qh15"),
    ("kỷ luật", datetime(2025, 6, 1), "law-36-2024-qh15"),
    ("phanh hệ thống lái đèn còi", datetime(2025, 6, 1), "law-36-2024-qh15"),
    ("cảnh báo người tham gia giao thông", datetime(2025, 6, 1), "law-36-2024-qh15"),
    # Unanswerable questions (no lexical match expected)
    ("neutrino lượng tử plasma", datetime(2025, 6, 1), None),
    ("zzquasar xxnebula yyapogee", datetime(2025, 6, 1), None),
    ("enzyme protein ribosome", datetime(2025, 6, 1), None),
    ("photosynthesis chlorophyll genome", datetime(2025, 6, 1), None),
    ("blockchain defi tokenomics", datetime(2025, 6, 1), None),
    ("kubernetes helm ingress", datetime(2025, 6, 1), None),
    ("quantum annealing qubit", datetime(2025, 6, 1), None),
    ("compiler bytecode runtime", datetime(2025, 6, 1), None),
    ("acid citric fermentation", datetime(2025, 6, 1), None),
    ("volcano basalt magma", datetime(2025, 6, 1), None),
    ("xylophone orchestra symphony", datetime(2025, 6, 1), None),
    ("satellite orbital apogee", datetime(2025, 6, 1), None),
    ("algebra topology manifold", datetime(2025, 6, 1), None),
    ("microscope electron diffraction", datetime(2025, 6, 1), None),
    ("meteorite isotope zircon", datetime(2025, 6, 1), None),
    ("penguin antarctic glacier", datetime(2025, 6, 1), None),
    ("espresso barista arabica", datetime(2025, 6, 1), None),
    ("opera soprano libretto", datetime(2025, 6, 1), None),
    ("basketball rebound timeout", datetime(2025, 6, 1), None),
    ("cryptography nonce cipher", datetime(2025, 6, 1), None),
    ("zzairframe xxrotorcraft yypilot", datetime(2025, 6, 1), None),
    ("zzalgebra xxtopology yymatrix", datetime(2025, 6, 1), None),
    ("zzbiology xxribosome yycellular", datetime(2025, 6, 1), None),
    ("đàn piano hợp âm", datetime(2025, 6, 1), None),
    ("zzchemistry xxbenzene yyorganic", datetime(2025, 6, 1), None),
    ("nhiệt động lực entropy", datetime(2025, 6, 1), None),
    ("robot hút bụi gia đình", datetime(2025, 6, 1), None),
    ("zzkernel xxsyscall yydaemon", datetime(2025, 6, 1), None),
    ("zztelescope xxradioastronomy yyobservatory", datetime(2025, 6, 1), None),
    # Pre-effective legal-looking questions
    ("đường bộ", datetime(2024, 12, 31), None),
    ("trật tự giao thông", datetime(2024, 12, 31), None),
    ("người lái xe", datetime(2024, 12, 31), None),
    ("phương tiện giao thông", datetime(2024, 12, 31), None),
    ("điều 1", datetime(2024, 12, 31), None),
    ("điều 10", datetime(2024, 12, 31), None),
    ("điều 43", datetime(2024, 12, 31), None),
    ("biển báo đường bộ", datetime(2024, 12, 31), None),
]


class TestRetrievalTestSuite(unittest.TestCase):
    """Run retrieval questions against fake retriever."""

    def setUp(self):
        self.retriever = FakeRetriever()
        self.retriever.add_chunk(sample_law_35_chunk())
        self.retriever.add_chunk(sample_law_36_chunk())

    def test_retrieval_question_coverage(self):
        """Verify we have at least 50 questions per Gate P3 spec."""
        self.assertGreaterEqual(
            len(RETRIEVAL_QUESTIONS),
            50,
            "Need 50+ questions per Gate P3 spec",
        )

    def test_answerable_questions_return_citations(self):
        """All answerable questions should return the expected first citation."""
        answerable = [q for q in RETRIEVAL_QUESTIONS if q[2] is not None]

        for query_text, scenario_time, expected_doc_id in answerable:
            with self.subTest(query=query_text):
                query = RetrievalQuery(query_text=query_text, scenario_time=scenario_time)
                result = self.retriever.retrieve(query)
                self.assertIsNone(result.structured_failure)
                self.assertGreater(len(result.citations), 0)
                self.assertEqual(result.citations[0].document_id, expected_doc_id)

    def test_unanswerable_questions_return_no_citations(self):
        """Unanswerable and pre-effective questions should return no citations."""
        unanswerable = [q for q in RETRIEVAL_QUESTIONS if q[2] is None]

        for query_text, scenario_time, _ in unanswerable:
            with self.subTest(query=query_text):
                query = RetrievalQuery(query_text=query_text, scenario_time=scenario_time)
                result = self.retriever.retrieve(query)
                self.assertEqual(len(result.citations), 0)


if __name__ == "__main__":
    unittest.main()
