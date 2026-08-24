"""Script to assemble the complete STWI Internship Report package.

Follows the university regulations (H1, M1, D2, D3) from Khoa KH&KT Máy tính - ĐHBK TP.HCM:
1. Cover page (Trang bìa & Trang tên chuẩn M1)
2. Form D2: Approved Internship Program (Chương trình TTNT đã duyệt có dấu mộc đỏ)
3. Form D3: Admission Result (Kết quả xét tuyển, if applicable)
4. Full Technical Report body (Thông tin thực tập, Tóm tắt, Mục lục, 11 chương kỹ thuật, Xác nhận bảo mật, Tài liệu tham khảo, Phụ lục)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = None  # type: ignore
    PdfWriter = None  # type: ignore


ROOT_DIR = Path(__file__).resolve().parents[2]
GUIDES_DIR = ROOT_DIR / "docs" / "guides" / "TTNT_HD_BM_HuongDan_BieuMau_ShareSV+CB"
D2_D3_DIR = (
    GUIDES_DIR
    / "HK253_TTNT_ShareSV+CB"
    / "HK253_TTNT_ShareDN+SV+GV"
    / "HK253_TTNT_D2&3"
)


def list_available_d2_forms() -> list[Path]:
    """Return all available D2 and D3 PDF files in the university repository."""
    if not D2_D3_DIR.exists():
        return []
    return sorted(list(D2_D3_DIR.glob("*.pdf")))


def assemble_report(
    *,
    main_pdf_path: Path,
    d2_pdf_path: Path | None = None,
    d3_pdf_path: Path | None = None,
    output_pdf_path: Path,
    allow_missing_d2: bool = False,
) -> Path:
    """Merge cover, D2, D3, and main report body into a compliant final PDF."""
    if PdfReader is None or PdfWriter is None:
        raise RuntimeError("pypdf is not installed. Please run `pip install pypdf`.")

    if not main_pdf_path.exists():
        raise FileNotFoundError(f"Main report PDF not found: {main_pdf_path}")
    if d2_pdf_path is None and not allow_missing_d2:
        raise ValueError(
            "A signed/approved D2 PDF is required for a submission package. "
            "Use --allow-missing-d2 only for an explicitly labelled draft."
        )
    if d2_pdf_path is not None and not d2_pdf_path.exists():
        raise FileNotFoundError(f"D2 PDF not found: {d2_pdf_path}")
    if d3_pdf_path is not None and not d3_pdf_path.exists():
        raise FileNotFoundError(f"D3 PDF not found: {d3_pdf_path}")

    main_reader = PdfReader(str(main_pdf_path))
    writer = PdfWriter()

    print("============================================================")
    print("GHÉP HỒ SƠ BÁO CÁO THỰC TẬP NGOÀI TRƯỜNG (TTNT HK253)")
    print("============================================================")

    # 1. Page 1: Cover / Trang bìa
    print(f"[1/4] Thêm Trang bìa chuẩn M1 từ: {main_pdf_path.name} (Trang 1)")
    writer.add_page(main_reader.pages[0])

    # 2. Form D2 (if provided)
    if d2_pdf_path and d2_pdf_path.exists():
        d2_reader = PdfReader(str(d2_pdf_path))
        print(
            f"[2/4] Chèn Form D2 (Chương trình đã duyệt): {d2_pdf_path.name} ({len(d2_reader.pages)} trang)"
        )
        for idx, page in enumerate(d2_reader.pages, start=1):
            writer.add_page(page)
    else:
        print("[2/4] Bỏ qua Form D2 (chỉ hợp lệ với bản DRAFT)")

    # 3. Form D3 (if provided)
    if d3_pdf_path and d3_pdf_path.exists():
        d3_reader = PdfReader(str(d3_pdf_path))
        print(
            f"[3/4] Chèn Form D3 (Kết quả xét tuyển): {d3_pdf_path.name} ({len(d3_reader.pages)} trang)"
        )
        for idx, page in enumerate(d3_reader.pages, start=1):
            writer.add_page(page)
    else:
        print("[3/4] Không chèn D3; chỉ hợp lệ khi sinh viên đã có tên trong D2")

    # 4. Remaining main report pages (Page 2 to end)
    remaining_pages = len(main_reader.pages) - 1
    print(
        f"[4/4] Thêm toàn bộ Nội dung Báo cáo & Phụ lục từ: {main_pdf_path.name} (Trang 2 đến {len(main_reader.pages)}: {remaining_pages} trang)"
    )
    for page in main_reader.pages[1:]:
        writer.add_page(page)

    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_pdf_path, "wb") as f_out:
        writer.write(f_out)

    total_pages = len(writer.pages)
    file_size_mb = output_pdf_path.stat().st_size / (1024 * 1024)

    print("------------------------------------------------------------")
    print("ĐÃ GHÉP GÓI PDF; TRẠNG THÁI NỘP PHỤ THUỘC CHỮ KÝ/XÁC NHẬN")
    print(f"Đường dẫn file: {output_pdf_path.resolve()}")
    print(f"Tổng số trang: {total_pages} trang")
    print(f"Dung lượng tệp: {file_size_mb:.2f} MB")
    print("============================================================")

    return output_pdf_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ghép nối Báo cáo thực tập tốt nghiệp STWI theo quy chế Khoa KH&KT Máy tính - ĐHBK"
    )
    parser.add_argument(
        "--main-pdf",
        type=Path,
        default=ROOT_DIR / "report" / "main.pdf",
        help="Đường dẫn đến tệp report/main.pdf đã biên dịch",
    )
    parser.add_argument(
        "--d2-pdf",
        type=Path,
        default=None,
        help="Đường dẫn tệp D2_*.pdf (Chương trình thực tập đã duyệt)",
    )
    parser.add_argument(
        "--d3-pdf",
        type=Path,
        default=None,
        help="Đường dẫn tệp D3_*.pdf (Kết quả xét tuyển)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=ROOT_DIR / "STWI_BaoCao_ThucTap_HK253_Complete.pdf",
        help="Đường dẫn tệp PDF đầu ra",
    )
    parser.add_argument(
        "--list-d2",
        action="store_true",
        help="Liệt kê các tệp D2/D3 có sẵn trong thư mục hướng dẫn của Khoa",
    )
    parser.add_argument(
        "--allow-missing-d2",
        action="store_true",
        help="Cho phép tạo bản DRAFT khi chưa có D2 PDF; không dùng cho bản nộp",
    )

    args = parser.parse_args(argv)

    if args.list_d2:
        forms = list_available_d2_forms()
        print(f"Tìm thấy {len(forms)} tệp biểu mẫu D2/D3 trong thư mục Khoa:")
        for idx, f in enumerate(forms[:30], start=1):
            print(f"  {idx:2d}. {f.name}")
        if len(forms) > 30:
            print(f"  ... và {len(forms) - 30} tệp khác.")
        return 0

    try:
        assemble_report(
            main_pdf_path=args.main_pdf,
            d2_pdf_path=args.d2_pdf,
            d3_pdf_path=args.d3_pdf,
            output_pdf_path=args.output,
            allow_missing_d2=args.allow_missing_d2,
        )
        return 0
    except Exception as exc:
        print(f"❌ LỖI: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
