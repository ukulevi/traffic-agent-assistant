# STWI hardened single-host production baseline

Baseline này mô tả topology Docker Compose đã được duyệt cho một host do đơn
vị vận hành kiểm soát. Nó không tự triển khai hệ thống và không phải bằng chứng
đủ để tuyên bố production-ready hay đạt SLA đo lường.

`infra/harness` vẫn là đường chạy demo/integration riêng. Không dùng file ở thư
mục đó làm production manifest và không đổi demo sang `STWI_RUNTIME_MODE=production`.

## Configuration preflight

1. Tạo file environment riêng ngoài Git từ danh sách tên biến trong
   `.env.example`. Không sao chép credential vào README, Linear hoặc log.
2. Đặt `STWI_APP_IMAGE` bằng image đã promote và pin theo dạng
   `registry/name@sha256:<64-hex>`.
3. Đặt thư mục artifact baseline/surrogate đã promote. Mỗi thư mục phải chứa
   manifest, model, checksum, calibration và expiry hợp lệ.
4. Production image phải cung cấp `stwi.production:app`,
   `stwi.production_worker:app`, trusted principal/UI-context providers và các
   real model adapters. Repository hiện không giả lập các thành phần này;
   thiếu chúng phải làm startup thất bại.
5. Chạy:

```powershell
python infra/production/ops.py preflight --project-name stwi-prod
```

Preflight chỉ hợp lệ khi validator và `docker compose config --quiet` cùng pass.
Không in nội dung file environment hoặc giá trị secret khi thu thập evidence.

## Migration

Migration dùng short-lived admin context; API/worker chỉ kết nối bằng
`stwi_reader_user` cho truy vấn mô phỏng. Sau khi backup và review migration:

```powershell
python infra/production/ops.py migration --project-name stwi-prod
```

Promoted image phải cung cấp `stwi.production_migrate`. Không chạy DDL từ API
process, không seed dữ liệu demo/test vào TimescaleDB production và không dùng
reader credential cho migration.

## Startup and readiness

Sau khi Human Review chấp thuận host, firewall, TLS ingress và secret injection:

```powershell
python infra/production/ops.py start --project-name stwi-prod
python infra/production/ops.py readiness --project-name stwi-prod
```

Chỉ API bind loopback theo mặc định. Redis, TimescaleDB và Qdrant không publish
host port. Readiness phải kiểm tra dependency thật và promoted artifacts; `/docs`
không phải health evidence. Trạng thái dependency lỗi phải fail closed và không
được tạo `recommended_action`.

## Backup and restore verification

Tạo thư mục backup riêng, được mã hóa và không nằm trong repository:

```powershell
python infra/production/ops.py backup --project-name stwi-prod --backup-dir D:\stwi-private-backups\2026-08-03
```

Lệnh tạo TimescaleDB dump, yêu cầu Redis persistence flush và yêu cầu promoted
application tạo Qdrant snapshot. Operator phải kiểm tra đủ ba artifact, quyền
truy cập, checksum, encryption và audit timestamp. CLI không xóa volume.

Restore chỉ được kiểm tra trong namespace tách biệt, không trỏ vào volume đang
chạy và cần xác nhận rõ:

```powershell
python infra/production/ops.py restore-verify --project-name stwi-restore-check --restore-source D:\stwi-private-backups\2026-08-03 --approved
```

Baseline hiện chỉ dựng preflight/namespace cho restore verification. Storage
mapping, key giải mã và kiểm tra dữ liệu phục hồi là Human Review gate theo host;
không được xem preflight đơn thuần là restore pass.

## Restart recovery

Sau khi tạo một job test aggregate-only và ghi lại `job_id`, chạy:

```powershell
python infra/production/ops.py restart-recovery --project-name stwi-prod
python infra/production/ops.py readiness --project-name stwi-prod
```

Xác nhận job/event vẫn đọc được từ Redis, terminal state không bị ghi đè và SSE
reconnect không chạy job lần hai. Không dùng video thô hoặc endpoint RTSP cho
smoke test này.

## Rollback

Rollback yêu cầu image digest trước đó, backup đã kiểm tra và review tương thích
migration. Operator cập nhật riêng `STWI_APP_IMAGE`, sau đó chạy:

```powershell
python infra/production/ops.py rollback --project-name stwi-prod --approved
python infra/production/ops.py readiness --project-name stwi-prod
```

Rollback chỉ thay API/worker, không tự downgrade database và không tự xóa dữ
liệu. Nếu schema không tương thích, dừng ở Human Review.

## Shutdown

```powershell
python infra/production/ops.py stop --project-name stwi-prod
```

`stop` dùng `docker compose down` nhưng không thêm `--volumes` hoặc `-v`. Xóa
volume là thao tác ngoài runbook này và cần quy trình retention riêng.

## Human Review gates

Các mục sau phải có chủ sở hữu và evidence riêng trước deployment thật:

- host ownership, OS hardening, firewall, TLS reverse proxy và DNS;
- registry access, promoted image digest và software bill of materials;
- trusted identity mapping, UI scope và rotation/revocation procedure;
- promoted baseline/surrogate artifacts và non-mock calibration;
- backup schedule, encryption/key custody, retention và restore drill;
- monitoring backend, alert routing, rate limit và on-call ownership;
- contract-profile surrogate/E2E benchmark của TRA-6 và TRA-48;
- privacy review cho camera/RTSP của TRA-11 và TRA-37;
- go/no-go production release của TRA-51.

Không gate nào ở trên được suy diễn là pass chỉ vì Compose config hoặc unit test
pass. STWI luôn là decision support, cần operator approval và không có automatic
actuation.
