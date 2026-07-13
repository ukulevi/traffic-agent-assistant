# MVP Operator Dashboard

Run the API with the existing orchestrator extra, then open `/demo/` on the
same origin. The screen creates a What-If job, reads its terminal result and
SSE events, then records an operator decision for audit only.

The dashboard is provisional and aggregate-only. It never displays raw video,
credentials, or an executable field action. For `needs_review`, it renders
only `candidate_action`; a recommendation is shown only for `succeeded`.

Every decision remains human-controlled: the UI requires an explicit approve
or reject action and records `applied_by_system=false`.
