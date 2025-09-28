# 1C assets and automation

This directory stores the text configuration dump that is used for regression
checks and the source code of the KMP4 delivery report external processing.
The helper scripts in `scripts/1c` allow you to refresh these artefacts from a
live 1C information base and verify that the committed tree matches the
reference snapshot.

## Prerequisites

The scripts are designed to run from the repository root on Windows and WSL and
rely on the following tools:

- **1C:Enterprise 8 Designer** (`1cv8`) must be installed and available in the
  `PATH`. The scripts do not hard-code an installation path so both native
  Windows and WSL interop (`/mnt/c/Program Files/.../1cv8.exe`) are supported.
- **PowerShell 7+** (`pwsh`) is required for running the `.ps1` utilities.
  Windows PowerShell 5.1 also works as long as `1cv8` is reachable.
- **Python 3.11+** to execute the verification helper.

> ℹ️ Pass the Designer connection arguments explicitly when invoking the
> PowerShell scripts. Typical examples include `@('/F', 'C:\\Bases\\MyBase')`
> for a file database or `@('/S', 'server\\db')` for a server publication.

## Repository layout

- `config_dump_txt/` — baseline text export of the configuration modules and
  templates used by regression tests.
- `external/kmp4_delivery_report/` — source tree of the KMP4 delivery report
  external processing (the `.epf` is built from this folder). The file
  `metadata.xml` contains the Designer metadata of the processing.
- `verification_manifest.json` — reference hashes and sizes that the verification
  script uses to ensure the tree has not changed unexpectedly.

## Usage

### Dump configuration to text

```
pwsh scripts/1c/dump_config_to_txt.ps1 -ConnectionArgs @('/F', 'C:\\Bases\\MyBase') -CleanOutput
```

The script:

1. Resolves all paths relative to the repository root, so it works both on
   Windows and in WSL.
2. Stores the Designer transcript in `build/1c/dump_config_to_txt.log`.
3. Refreshes `1c/config_dump_txt/` with the textual export. Use `-CleanOutput`
   to wipe previous dumps before exporting.

### Package the external processing

```
pwsh scripts/1c/pack_external_epf.ps1 -ConnectionArgs @('/F', 'C:\\Bases\\MyBase')
```

This command packages `1c/external/kmp4_delivery_report/src/` into
`build/1c/kmp4_delivery_report.epf`. The log is written to
`build/1c/pack_kmp4.log`. Use `-Overwrite` if the target file already exists, or
customise the source/output paths with `-SourceDirectory` / `-OutputFile`.

### Verify the committed tree

```
python scripts/1c/verify_1c_tree.py
```

`verify_1c_tree.py` loads `1c/verification_manifest.json` and validates file
presence, size, and SHA-256 hashes for the configuration dump and external
processing source. The script exits with a non-zero code on any mismatch. If you
intentionally refresh the dump or external processing, regenerate the manifest
before committing:

```
python - <<'PY'
import hashlib, json, pathlib
repo = pathlib.Path('.').resolve()
entries = {}
for key, rel in {
    'config_dump_txt': '1c/config_dump_txt',
    'external_kmp4_delivery_report': '1c/external/kmp4_delivery_report',
}.items():
    base = repo / rel
    files = {}
    for file in sorted(base.rglob('*')):
        if file.is_file():
            data = file.read_bytes()
            files[str(file.relative_to(base)).replace('\\', '/')] = {
                'size': len(data),
                'sha256': hashlib.sha256(data).hexdigest(),
            }
    entries[key] = {'base_path': rel, 'files': files}
(repo / '1c' / 'verification_manifest.json').write_text(
    json.dumps(entries, ensure_ascii=False, indent=2),
    encoding='utf-8',
)
PY
```

Always run the verification script after updating the manifest to make sure the
snapshot is consistent.
