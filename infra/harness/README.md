# Harness Open Source cho môi trường local

Cấu hình này chạy image chính thức của [Harness Open Source](https://github.com/harness/harness) tách biệt với runtime STWI. Database và repository được giữ trong các Docker named volume `stwi-harness-data` và `stwi-harness-git`. Cấu hình mặc định không cấp quyền truy cập Docker daemon cho Harness.

## Yêu cầu

- Docker Desktop đang chạy với Linux containers.
- Hai cổng `3000` và `3022` đang trống. Nếu bị trùng, sao chép `.env.example` thành `.env` và đổi cổng host.

## Khởi động

Từ thư mục repository:

```powershell
docker compose --env-file infra/harness/.env.example -f infra/harness/compose.yaml up -d
docker compose -f infra/harness/compose.yaml ps
```

Mở <http://localhost:3000>. Tài khoản khởi tạo mặc định theo upstream là `admin` / `changeit`; hãy đổi mật khẩu ngay sau lần đăng nhập đầu tiên.

Nếu đã tạo `infra/harness/.env`, dùng lệnh sau thay cho lệnh khởi động ở trên:

```powershell
docker compose --env-file infra/harness/.env -f infra/harness/compose.yaml up -d
```

## Vận hành

Xem log:

```powershell
docker compose -f infra/harness/compose.yaml logs -f harness
```

Dừng dịch vụ nhưng giữ dữ liệu:

```powershell
docker compose -f infra/harness/compose.yaml down
```

## Bật pipeline và Gitspace dùng Docker

Chế độ mặc định phù hợp để dùng UI, code hosting và artifact registry. Pipeline hoặc Gitspace cần tạo container phải có quyền truy cập Docker daemon. Chỉ bật sau khi đã chấp nhận rủi ro quản trị host:

```powershell
docker compose `
  -f infra/harness/compose.yaml `
  -f infra/harness/compose.docker-access.yaml `
  up -d
```

Nâng cấp có chủ đích bằng cách lấy digest mới của `harness/harness`, cập nhật trường `image`, rồi chạy lại `docker compose up -d`. Không dùng `down --volumes` nếu chưa chủ động muốn xóa toàn bộ repository, pipeline và cấu hình trong Harness.

## Lưu ý an toàn

Override `compose.docker-access.yaml` mount Docker socket để chạy pipeline và Gitspace. Quyền này cho container điều khiển Docker daemon, tương đương quyền quản trị host trong thực tế. Chỉ bật override khi thật sự cần, chỉ chạy image đã pin, không chạy pipeline không tin cậy và không đưa secret STWI vào repository/pipeline nếu chưa cấu hình secret management phù hợp.

Harness là công cụ DevOps local, không phải thành phần runtime của STWI và không thay đổi `project_contract.json`.

## Không chạy Roboflow Inference Server local

**Đừng** chạy `roboflow/roboflow-inference-server-gpu` hoặc `roboflow/roboflow-inference-server-cpu` trong Docker. Image này ngốn ~2.7 GB RAM khi idle và không được dùng bởi bất kỳ thành phần runtime nào của STWI.

STWI gọi thẳng **Roboflow Cloud API** (`https://serverless.roboflow.com`) qua `inference-sdk` — không cần server local. MCP server (`scripts/roboflow_mcp_server.py`) là một tiến trình stdio nhẹ, chạy trực tiếp bằng Python, không cần Docker.
