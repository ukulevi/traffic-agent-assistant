# Bản đối chiếu tiếng Việt cho báo cáo TTNT HK253

## Mục đích

Tạo một PDF tiếng Việt để sinh viên đối chiếu cách trình bày với mẫu M1/H1
của Khoa. Đây không phải bản nộp chính thức vì sinh viên thuộc chương trình
CC phải nộp báo cáo tiếng Anh.

## Phạm vi

- Giữ nguyên dữ kiện, cấu trúc và thứ tự của báo cáo TTNT tiếng Anh hiện có:
  bìa M1, D2, quá trình thực tập, sản phẩm/kỹ năng/kiến thức, cảm nhận và
  xác nhận của sinh viên/doanh nghiệp.
- Dịch các tiêu đề và nội dung tự sự sang tiếng Việt; không thay đổi tên hệ
  thống, mã môn CO3335, định danh kỹ thuật, kết quả hay giới hạn STWI.
- Bổ sung tên cán bộ hướng dẫn doanh nghiệp đã được người dùng xác nhận:
  **Võ Tấn Phát (VNPT-IT)**, trên cả bìa và khối xác nhận doanh nghiệp.
- Gắn nhãn nổi bật `BẢN ĐỐI CHIẾU – KHÔNG NỘP CHÍNH THỨC` trên bìa.
- Giữ bản tiếng Anh là bản nộp chính thức; cập nhật tên CBHD vào bản này để
  phản ánh thông tin đã được xác nhận.

## Đầu ra

1. PDF tiếng Anh CBHD-review, đã điền Võ Tấn Phát (VNPT-IT).
2. Gói PDF tiếng Anh ghép bìa → D2 → nội dung.
3. PDF tiếng Việt đối chiếu có nhãn không nộp chính thức.

## Kiểm tra chấp nhận

- Bìa tuân theo bố cục M1 và thể hiện đủ trường H1 bằng đúng ngôn ngữ của
  từng bản.
- Hai bản có cùng dữ kiện cá nhân, doanh nghiệp, thời gian và cấu trúc.
- D2 chỉ được ghép vào gói tiếng Anh phục vụ quy trình nộp; bản Việt dùng để
  đối chiếu, không được hiểu là bản nộp thay thế.
- XeLaTeX dựng thành công; PDF được render và kiểm tra trực quan.
