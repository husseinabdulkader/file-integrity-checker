# Verification record

Date: 2026-11-10. Environment: Windows, Python 3.14.2. Scope: local sample files and temporary test directories.

`python -m unittest discover -s tests -v` discovered 15 tests. Fourteen passed; the symbolic-link test was skipped because this account cannot create symbolic links. These are the original local results; hosted validation is recorded below. No live operational deployment is claimed.

The known SHA-256 test checks the fixed `abc` test vector. The combined-change test independently expects a same-size content edit to be modified, a new path to be added and a removed path to be removed. CLI tests confirm exits 0, 1 and 2 and that attempts to overwrite a baseline leave its original bytes intact. Permission-error behaviour is tested by injecting a read failure; actual Windows ACL scenarios were not exercised.

The two sample files contain fictional configuration/notes text. Separate temporary copies were used for CLI reproduction. The original sample files were not modified during verification.

## Reproduction result

1. Created a baseline of two copied sample files: exit 0.
2. Compared the unchanged copy: exit 0, unchanged_count 2.
3. Appended a line to settings.txt in the temporary copy: check exited 1, modified contained settings.txt, unchanged_count 1.

These observations establish basic content comparison, not attack attribution, complete tamper resistance or production performance. No performance benchmark was run.

## Automated CLI demonstration

On 2026-11-10, `python demo.py` completed all seven scenarios successfully. Each scenario creates a fresh baseline against a temporary copy and asserts the exact exit code and result. [Recorded JSON](demo-results.json) contains the observed outcomes without local paths or file contents.

| Scenario | Exit code | Observed result |
| --- | --- | --- |
| Unchanged | 0 | Two unchanged files |
| Modified | 1 | settings.txt reported modified |
| Added | 1 | new.txt reported added |
| Removed | 1 | notes.txt reported removed |
| Renamed | 1 | notes.txt removed and renamed-notes.txt added |
| Baseline overwrite attempted | 2 | Error reported; original baseline bytes preserved |
| Malformed baseline | 2 | Error reported; no clean result emitted |

The original sample bytes were compared before and after the demonstration and matched. A separate check of the existing `baseline.json` against `samples` returned exit 0 and unchanged_count 2. The local test suite was rerun: 14 passed, with the same one symbolic-link test skipped. Subsequent hosted validation is recorded below.

## GitHub verification

Published on 2026-11-10. [Workflow run 42767541989](https://github.com/husseinabdulkader/file-integrity-checker/actions/runs/42767541989) completed successfully for commit `a52906ee6e11bfaad8b92d102247a4a955472603`. Both Windows and Ubuntu jobs passed the test-suite and demonstration steps with Python 3.14. This verifies the automated checks on both hosted platforms; the original local symbolic-link skip remains documented separately. Personal baseline files were excluded from publication.
