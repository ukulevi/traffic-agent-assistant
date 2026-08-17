# Repository Hygiene Refactor Design

**Ngày:** 2026-08-17
**Trạng thái:** Đã được người dùng duyệt trong phiên thiết kế
**Phạm vi:** Cấu trúc repository, ranh giới public/private, tài liệu cũ, CLI tooling, cleanup và quy trình publish GitHub

## 1. Bối cảnh

STWI hiện có cấu trúc cấp cao phù hợp với một dự án Python MVP: `src/`,
`scripts/`, `tests/`, `docs/`, `report/`, `slides/`, `infra/` và `data/`.
Audit read-only ngày 2026-08-17 ghi nhận:

- 436 file đang được Git theo dõi;
- 481 file chưa được theo dõi, trong đó khoảng 662 MB là biểu mẫu/tài liệu
  thực tập và khoảng 25,6 MB là render hoặc dữ liệu tạm;
- 26 tham chiếu tới script cũ không còn tồn tại tại đường dẫn được ghi trong
  README/runbook;
- một liên kết Markdown tương đối bị hỏng trong tài liệu kế hoạch;
- `.env.local` đang được ignore và không được Git theo dõi;
- thay đổi CI chưa commit có thể build và upload internship-report PDF;
- repository GitHub hiện là public;
- verifier hiện hành trên baseline `main` pass trước khi tạo spec này.

Worktree chính đang chứa thay đổi feature `network-impact/dashboard`. Feature
đó và refactor repository phải được review bằng hai draft PR độc lập.

## 2. Mục tiêu

1. Giữ repository công khai chỉ chứa mã nguồn, tài liệu và metadata STWI được
   phép công khai.
2. Làm rõ trách nhiệm của từng thư mục mà không di chuyển hàng loạt hoặc thay
   đổi contract/runtime.
3. Sửa toàn bộ đường dẫn script và liên kết tài liệu đang lỗi trong phạm vi
   active docs.
4. Giữ CLI trong `scripts/` mỏng; logic tái sử dụng phải nằm trong `src/stwi/`.
5. Dọn artifact có thể tái tạo mà không xóa dữ liệu private của người dùng.
6. Chặn fail-closed trước commit/push khi staged/tracked set chứa private file,
   secret pattern đáng ngờ hoặc generated artifact.
7. Publish qua feature branch và draft PR; không push trực tiếp lên `main`.

## 3. Ngoài phạm vi

- Không đổi `project_contract.json`, tensor shape, feature order, SLA, stack,
  API status hoặc human-approval semantics.
- Không tái thiết kế dashboard, slide hoặc visual language.
- Không chia lại `src/stwi/t4_orchestrator/api.py` hay orchestrator trong PR
  refactor vì các file này đang chồng với feature `network-impact`.
- Không sửa nội dung, chữ ký hoặc thông tin cá nhân trong báo cáo thực tập và
  biểu mẫu trường/doanh nghiệp.
- Không xóa `docs/archive/`, design/spec/plan history hoặc vendored Leaflet chỉ
  vì chúng không thuộc runtime Python.
- Không thêm framework hoặc dependency mới.

## 4. Cấu trúc đích

Các thư mục cấp cao được giữ ổn định:

```text
src/stwi/        logic có thể import, unit test và tái sử dụng
scripts/         CLI wrapper theo data_prep/training/validation/infra/demo
tests/           contract, tier T1-T4, frontend, tooling và operations
docs/            canonical docs, guides, design, ops, plans/specs và archive
report/          báo cáo kỹ thuật công khai sinh từ nguồn sự thật
slides/          slide công khai được GitHub Pages publish
infra/           harness local và production deployment contracts
data/manifests/  metadata công khai; không chứa raw/private dataset
```

Không tạo `apps/`, `packages/` hoặc monorepo layer mới. Cấu trúc hiện hành đủ
cho MVP 13 tuần; refactor tập trung vào ownership và hygiene.

## 5. Ranh giới public/private/generated

### 5.1 Public và được phép tracked

- `src/stwi/`, CLI wrapper, tests, canonical docs, public runbook;
- technical report và public slides;
- schema, example environment file chỉ chứa placeholder;
- dataset manifest đã được review, không chứa raw media hoặc secret.

### 5.2 Private local: giữ nguyên dữ liệu, không tracked

- thư mục biểu mẫu `docs/guides/TTNT_HD_BM_HuongDan_BieuMau_ShareSV+CB/`;
- `report/internship_main.tex` và các chapter/figure chỉ dành cho báo cáo thực
  tập;
- `.env`, `.env.local`, `.env.*.local`;
- raw media, private dataset, model weight và review pack.

Các đường dẫn này được thêm đồng thời vào `.gitignore` và `.codexignore` để
giảm nguy cơ stage nhầm và giảm việc agent/tooling đọc dữ liệu không cần thiết.
Không tự động di chuyển hoặc chỉnh nội dung các file private.

### 5.3 Generated local: có thể xóa sau kiểm tra

- `tmp/`, `output/`, render tạm;
- `__pycache__/`, `.pytest_cache/`, `*.egg-info/`;
- LaTeX build output, local site output và video showcase output;
- các artifact khác đã có nguồn hoặc lệnh tái tạo xác định.

Cleanup chỉ chạy trên đường dẫn tuyệt đối đã kiểm tra nằm trong repository.
Không dùng glob hoặc recursive delete trên target chưa resolve. Trước khi xóa,
phải xác nhận target không tracked và không thuộc nhóm private-local.

## 6. Thay đổi tài liệu

1. Rút gọn root `README.md` thành overview, quickstart, repository map, privacy
   boundary và liên kết tới runbook chi tiết.
2. Cập nhật các command cũ sang nhóm script hiện hành:
   `scripts/data_prep/`, `scripts/training/`, `scripts/validation/` hoặc
   `scripts/infra/`.
3. Cập nhật `docs/guides/repository_structure.md` để mô tả đủ `demo/`,
   `project_management/`, `report/`, production modules và local-only data.
4. Sửa active-doc links bị hỏng. Tài liệu lịch sử chỉ sửa link kỹ thuật rõ
   ràng; không viết lại quyết định lịch sử.
5. Mở rộng validator tài liệu để command tham chiếu tới local script phải tồn
   tại. Điều này ngăn README/runbook tiếp tục drift sau refactor.

Canonical docs được sửa trước khi đồng bộ derived artifact nếu nội dung STWI
thực sự thay đổi. Refactor này không thay đổi contract nên không sửa report/
slides chỉ để tạo churn.

## 7. Chuẩn hóa CLI tooling

`scripts/benchmark_external_vision_model.py` đang chứa logic tái sử dụng. Logic
benchmark, summary và verdict assembly sẽ được chuyển vào module tập trung dưới
`src/stwi/tooling/vision_training/`. File script gốc được giữ làm wrapper tương
thích, chỉ parse argument, gọi module và trả exit code.

Các script khác không được di chuyển hàng loạt trong PR này. Đường dẫn mới đã
tồn tại trong các nhóm con sẽ trở thành đường dẫn canonical trong docs; wrapper
gốc chỉ được giữ khi đã có compatibility contract rõ ràng.

## 8. Privacy guard

Một validator không dependency mới sẽ kiểm tra tracked/staged repository:

- denylist cho internship source, school/company forms, local environment,
  raw media, weight, render/cache và private dataset paths;
- high-confidence token/private-key patterns trên text files, chỉ báo path và
  rule, không in secret value;
- example env chỉ hợp lệ khi dùng placeholder, không dùng credential thật;
- CI workflow không được build hoặc publish private internship artifact;
- documented local script path phải resolve tới file tồn tại.

Validator có unit tests cho allow/deny cases và được gọi trong fast CI cùng
contract/docs guards. Khi có nghi vấn, validator fail closed và yêu cầu human
review; không tự xóa hoặc tự redact credential.

## 9. Trình tự Git và PR

### 9.1 Draft PR feature hiện tại

- Branch hiện tại chỉ stage `network-impact/dashboard` code, tests, public docs
  và technical-report changes thuộc feature.
- Loại khỏi staged set: internship report, biểu mẫu, render tạm và thay đổi CI
  upload internship PDF.
- Chạy targeted tests, full STWI verifier, PDF build và visual QA cho các trang
  report bị ảnh hưởng.
- Push branch và mở draft PR; không merge tự động.

### 9.2 Draft PR refactor

- Branch `codex/repository-hygiene-refactor` được tạo độc lập từ `main`.
- Commit spec trước, sau đó implementation theo plan được duyệt.
- Stage explicit paths, chạy privacy guard và release QA, rồi mở draft PR riêng.
- PR không phụ thuộc feature PR trừ khi một file thực sự chồng nhau; nếu có,
  rebase/resolve chỉ sau khi người dùng chọn thứ tự merge.

## 10. Verification và acceptance criteria

Các kiểm tra tối thiểu:

```powershell
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1
```

Thêm targeted tests cho CLI benchmark extraction, documented-script resolver
và privacy guard. Dùng `-BuildPdf` và visual QA khi PR feature sửa report.

Refactor đạt acceptance khi:

- không có private/generated path trong tracked hoặc staged set;
- `.env.local`, internship sources và school/company forms vẫn tồn tại local
  nhưng Git/Codex bỏ qua;
- mọi documented script command trong active docs trỏ tới file tồn tại;
- CLI benchmark wrapper không còn business logic tái sử dụng;
- privacy guard có test và chạy trong CI;
- contract, docs, JavaScript, whitespace và targeted tests đều pass;
- hai draft PR tách scope và không push trực tiếp `main`.

## 11. Rủi ro và giảm thiểu

- **Xóa nhầm dữ liệu:** chỉ cleanup generated path đã resolve, không xóa nhóm
  private-local và báo rõ target đã xóa.
- **Trộn diff feature/refactor:** dùng linked worktree và explicit staging.
- **Docs drift:** validator kiểm tra path script trong active docs.
- **False positive secret scan:** chỉ dùng pattern độ tin cậy cao; hit dẫn tới
  human review, không tự sửa.
- **Compatibility CLI:** giữ wrapper gốc cho entrypoint đã được công bố.
- **CI artifact leak:** deny private report source/artifact và kiểm tra workflow
  trước push.
