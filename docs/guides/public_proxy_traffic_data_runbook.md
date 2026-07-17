# Public-proxy traffic data runbook (demo only)

This runbook creates an aggregate-only dataset for the offline MVP demo when
the local RTSP source and physical sensors are unavailable. It does not turn a
public dataset into local operational evidence, nor does it calibrate or
validate a real-world intervention.

## Preconditions

The data owner must download the archive under the provider's terms and place
it outside version control, for example under `data/external/public_proxy/`.
Do not automate sign-up, scrape access-controlled archives, or store provider
credentials in this repository. The input must be one rectangular CSV with
these fields:

```text
timestamp,source_node_id,traffic_volume_5m,avg_speed_kmh
```

`timestamp` is ISO-8601 with an offset. The input is already at five-minute
intervals; the importer intentionally refuses resampling, gaps, duplicate
records, unknown source nodes, negative values and fewer than 64 timestamps.

Create a separate JSON spec (also outside version control if it contains
restricted provider metadata). It must declare:

- `data_classification: "public_proxy_demo_only"`;
- provider URL, licence reference, downloader confirmation and download time;
- a clear non-representativeness notice;
- exactly 20 mapped proxy nodes, each with declared capacity and free-flow
  speed; and
- a finite, symmetric `20 x 20` adjacency matrix.

The declared capacity is proxy-network metadata. It is not a claim about a
Vietnamese junction or a local field capacity.

## Import

```powershell
python scripts/data_prep/ingest_public_proxy_traffic.py `
  --input-csv data/external/public_proxy/traffic_5min.csv `
  --spec data/external/public_proxy/public_proxy_spec.json `
  --output data/derived/private/phase1_public_proxy_v1
```

The importer records the input SHA-256 and source declaration in
`dataset_manifest.json`, preserves physical target units in `Y`, uses a
chronological split, and fits the scaler only on training data. Only volume,
speed and deterministic time features are observed. Environmental, heavy
vehicle and signal features remain false in `M` and are imputed with the
existing quality policy; they are not invented as observations.

Then run the normal quality gate and baseline evaluation. The existing P1
validator is mock/load-test specific, so it must not be used to relabel this
dataset as Gate-P1 production evidence. Review the manifest instead and retain
the following constraints in every demo screen and report:

- `data_classification = public_proxy_demo_only`;
- `production_representativeness = not_claimed`;
- `intervention_calibration_eligible = false`.

This dataset can exercise forecasting and the demo workflow. It cannot close
the local-data or field-calibration blockers.
