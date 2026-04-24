# Inspection, policy-read, and rubric tools

Read-only tools keep agents from scanning the filesystem directly.

- Workspace context: `brand_context_snapshot`, `brand_source_knowledge`, `brand_capabilities`, `brand_list_brands`, `brand_get_policy`
- Run/artifact projection: `brand_list_runs`, `brand_get_run`, `brand_get_plan`, `brand_get_critique`, `brand_get_scratchpad`, `brand_get_review_packet`, `brand_get_version`, `brand_compare_versions`, `brand_get_pending_reviews`
- Memory/calibration: `brand_show_blackboard`, `brand_show_iteration_memory`, `brand_show_rubric`, `brand_show_disagreements`, `brand_scoring_status`
- Rubric packet: `brand_critique_rubric`

Agents should prefer these projections over path guessing.
