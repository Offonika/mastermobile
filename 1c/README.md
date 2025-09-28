# 1C Assets Layout

This directory collects artifacts exported from the 1C platform that are consumed by integration scripts.

- `config_dump_txt/` — plain-text configuration fragments extracted from the legacy core subset. They are now grouped here so tooling can treat the folder as a canonical dump.
- `external/kmp4_delivery_report/` — delivery report extension (`КМП4`) sourced from the upstream repository. The unpacked configuration lives in `src/`, and the packaged XML artifact is stored alongside it.

The tree is designed to let automation discover configuration and vendor deliverables without relying on historical paths such as `core_subset/` or `src/`.
