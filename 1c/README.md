# 1C Assets Layout

This directory collects artifacts exported from the 1C platform that are consumed by integration scripts.

- `config_dump_txt/` — plain-text configuration fragments extracted from the legacy core subset. They are now grouped here so tooling can treat the folder as a canonical dump.
- `external/kmp4_delivery_report/` — delivery report extension (`КМП4`) sourced from the upstream repository. The unpacked configuration lives in `src/`, and the packaged XML artifact is stored alongside it.

The tree is designed to let automation discover configuration and vendor deliverables without relying on historical paths such as `core_subset/` or `src/`.

## Automation helpers

> **Prerequisites**
>
> - PowerShell 5.1+ (Windows) or PowerShell 7+ (Windows/WSL) with access to the repository root.
> - The 1C:Enterprise 8 platform installed locally and available via the `1cv8` CLI executable.
> - Permissions to access the target infobase (file or server) for design operations.

The `scripts/1c` directory contains utility scripts that operate purely on relative paths so they can be executed both on native Windows hosts and inside WSL sessions:

- `dump_config_to_txt.ps1` — wraps `1cv8 DESIGNER /DumpConfigToFiles` and streams a transcript to `build/1c/dump_config_to_txt.log`. Run it with either `-FileInfobasePath` or `-ServerInfobase` (plus optional `-User`/`-Password`) to update the canonical dump in `config_dump_txt/`.
- `pack_external_epf.ps1` — packages `external/kmp4_delivery_report/src/` into `external/kmp4_delivery_report/КМП4.epf`, writing the transcript to `build/1c/pack_kmp4.log`. Use the `-AsReport` switch if the artifact should be treated as an external report instead of a data processor.
- `verify_1c_tree.py` — validates that the checked-in dumps and extension sources match the expected manifest (file presence, size, and SHA-256 checksum). Invoke it with `python scripts/1c/verify_1c_tree.py`; any deviation results in a non-zero exit code and a detailed error list.
