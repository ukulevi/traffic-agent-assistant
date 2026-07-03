# STWI Repository Structure

Tai lieu nay mo ta ranh gioi thu muc sau refactor tooling. Muc tieu la giu
contract STWI on dinh, dong thoi lam ro noi dat logic co the import/test va noi
dat CLI wrapper.

## Nguyen tac

- `src/stwi/` chua logic co the import, unit test va tai su dung.
- `scripts/` chi nen parse tham so CLI, goi logic trong `src/stwi/`, in ket qua
  va tra exit code.
- `tests/` phan theo contract/tier/tooling de doc nhanh muc dich test.
- `data/external/` va `data/derived/private/` la du lieu sinh ra hoac rieng tu,
  khong commit raw media, weight, archive hoac secret.
- `docs/`, `report/`, `slides/` la artifact tai lieu; thay doi contract/API phai
  dong bo theo AGENTS.md.

## Layout hien tai

```text
src/stwi/
  contracts/                  # project and knowledge contracts
  config/                     # runtime settings
  t1_pipeline/                # data, vision evidence, tensor builder
  t2_forecast/                # baseline, surrogate, forecast safety
  t3_knowledge/               # retrieval, citation, query facade
  t4_orchestrator/            # API, job store, workflow, safety loop
  tooling/
    vision_training/          # reusable detector tooling logic
  utils/                      # small shared helpers

scripts/
  data_prep/                  # CLI entrypoints for data preparation
  training/                   # CLI entrypoints for training/promotion
  validation/                 # CLI entrypoints for gates and diagnostics
  infra/                      # admin/integration CLI entrypoints
  archive/                    # historical tooling only

tests/
  contracts/                  # machine-readable contract checks
  t1_pipeline/                # Tier 1 runtime and integration tests
  t2_forecast/                # Tier 2 model/safety tests
  t3_knowledge/               # Tier 3 RAG/query/security tests
  t4_orchestrator/            # Tier 4 API/workflow/safety tests
  vision/                     # vision tooling and detector artifact tests
```

## Vision tooling ownership

Reusable detector tooling now lives in:

- `src/stwi/tooling/vision_training/promotion.py`: promotion gate, required STWI
  classes, model artifact promotion.
- `src/stwi/tooling/vision_training/external_models.py`: HTTPS/checksum
  validation, external model manifest registration, class-map helpers, external
  benchmark verdict logic.

Compatibility CLI wrappers remain in `scripts/`:

- `scripts/training/promote_vision_model.py`
- `scripts/infra/fetch_external_vision_model.py`
- `scripts/infra/register_external_vision_model.py`
- `scripts/benchmark_external_vision_model.py`

Do not add new reusable logic to these wrappers. Put new functions in
`src/stwi/tooling/vision_training/` and import them from the CLI wrapper.

## Test layout for vision tooling

`tests/vision/test_local_vision_training.py` is now a compatibility entrypoint
for direct old test commands. The concrete tests are split by responsibility:

- `test_vision_dataset_preparation.py`
- `test_vision_dataset_augmentation.py`
- `test_vision_relabel_and_promotion.py`
- `test_external_vision_models.py`

Add new tests to the specific module instead of growing the compatibility
entrypoint.
