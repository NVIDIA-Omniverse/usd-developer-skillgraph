# Pinned Spec Materialization

This directory is for local copies of the spec sections used by a run.

The canonical source for this prototype is:

```text
repo: aousd/specifications-public
spec_version: 1.0.1   (core/1.0.1/core_spec.md)
```

`aousd/specifications-public` publishes the Core Spec as a single consolidated
markdown file, `core/<version>/core_spec.md`, and tracks only `main` (no version
tags). The materializer reads that file and carves out the per-section excerpts
under `spec/pinned/`. Run from the repo root with a fresh clone:

```bash
git clone https://github.com/aousd/specifications-public.git
./materialize-spec.sh --source-repo ./specifications-public
```

```powershell
git clone https://github.com/aousd/specifications-public.git
.\materialize-spec.ps1 -SourceRepo .\specifications-public
```

Because the public repo has no `v1.0.1` tag, the default `--commit v1.0.1`
doesn't resolve; the materializer falls back to the checkout's `HEAD` and records
that commit in `SPEC_PIN.txt`. Pass `--spec-version <X.Y.Z>` to pick a specific
`core/<version>/` directory (default `1.0.1`, falling back to the latest
published version), or `--commit <ref>` to pin a specific commit.

The Bash wrapper uses the same long flags as the Python materializer, including
`--source-repo`, `--spec-version`, `--out-dir`, `--commit`, and `--worktree-dir`.
The Python materializer also accepts `AOUSD_SPECIFICATIONS_PUBLIC_REPO` as the
source checkout path. A source checkout is required.

The script writes selected markdown files to `spec/pinned/`. Those files should
be treated as run inputs. The graph and skills cite the pinned tag / commit, not
the mutable working checkout.
