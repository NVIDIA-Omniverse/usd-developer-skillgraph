#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Materialize pinned USD Core Spec excerpts for the skillgraph.

The only supported source is a pinned tag-or-commit checkout of
aousd/specifications-public, because it contains authored markdown with stable
anchors.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Iterable


DEFAULT_COMMIT = "v1.0.1"

DEFAULT_SPEC_VERSION = "1.0.1"

PINNED_FILES = [
    Path("specification/foundational_data_types/README.md"),
    Path("specification/document_data_model/README.md"),
    Path("specification/composition/README.md"),
    Path("specification/path_grammar/README.md"),
    Path("specification/resource_interface/README.md"),
    Path("specification/file_formats/README.md"),
    Path("specification/stage_population/README.md"),
]

# aousd/specifications-public publishes the Core Spec as a single consolidated
# markdown file, core/<version>/core_spec.md, with top-level `# <Title>` section
# headings — not as per-section specification/<name>/README.md files, and with no
# version tags (only `main`). Map each spec section title to its pinned output path.
MARKDOWN_SECTIONS = [
    ("Foundational Data Types", Path("specification/foundational_data_types/README.md")),
    ("Document Data Model",     Path("specification/document_data_model/README.md")),
    ("Paths",                   Path("specification/path_grammar/README.md")),
    ("Resource Interface",      Path("specification/resource_interface/README.md")),
    ("Composition",             Path("specification/composition/README.md")),
    ("Stage Population",        Path("specification/stage_population/README.md")),
    ("Core File Formats",       Path("specification/file_formats/README.md")),
]

class MaterializeError(RuntimeError):
    pass


def run_checked(cmd: list[str], *, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise MaterializeError(f"command failed: {' '.join(cmd)}\n{detail}")
    return proc.stdout.strip()


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def default_worktree_dir(root: Path, commit: str) -> Path:
    return root / ".spec-worktrees" / f"specifications-public-{commit[:7]}"


def resolve_source_repo(value: str | None) -> Path | None:
    if value:
        return Path(value).expanduser().resolve()

    env_value = os.environ.get("AOUSD_SPECIFICATIONS_PUBLIC_REPO")
    if env_value:
        return Path(env_value).expanduser().resolve()

    return None


def resolve_pin(source_repo: Path, commit: str) -> tuple[str, str]:
    """Resolve a pin commit, tolerating refs that don't exist.

    aousd/specifications-public publishes only `main` (no version tags), so the
    historical default of `git rev-parse v1.0.1` fails on a fresh public clone.
    Fall back to the checked-out HEAD and record that as the pin.
    Returns (resolved_commit_sha, pin_label).
    """
    try:
        sha = run_checked(["git", "-C", str(source_repo), "rev-parse", f"{commit}^{{commit}}"])
        return sha, commit
    except MaterializeError:
        head = run_checked(["git", "-C", str(source_repo), "rev-parse", "HEAD"])
        print(
            f"materialize-spec: ref '{commit}' not found in {source_repo} "
            f"(the public spec repo publishes no version tags); pinning HEAD {head[:9]} instead.",
            file=sys.stderr,
        )
        return head, "HEAD"


def find_consolidated_spec(root: Path, spec_version: str | None) -> tuple[Path | None, str | None]:
    """Locate the consolidated core/<version>/core_spec.md published by
    aousd/specifications-public. Returns (path, version), or (None, version)
    if no consolidated spec is present (caller falls back to the legacy layout)."""
    core = root / "core"
    if spec_version:
        cand = core / spec_version / "core_spec.md"
        if cand.exists():
            return cand, spec_version
    if core.is_dir():
        versions = sorted(p.name for p in core.iterdir() if (p / "core_spec.md").exists())
        if versions:
            latest = versions[-1]
            return core / latest / "core_spec.md", latest
    return None, spec_version


def markdown_section(text: str, title: str) -> str:
    """Extract a top-level (`# Title`) section from consolidated spec markdown,
    running to the next top-level heading."""
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == f"# {title}":
            start = idx
            break
    if start is None:
        raise MaterializeError(f"section heading not found in core_spec.md: '# {title}'")
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if re.match(r"^# \S", lines[idx]):
            end = idx
            break
    return "\n".join(lines[start:end]).strip() + "\n"


def materialize_from_consolidated_markdown(
    spec_md: Path,
    out_dir: Path,
    spec_version: str,
    pinned_ref: str,
    resolved_commit: str,
) -> None:
    text = spec_md.read_text(encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    for title, rel in MARKDOWN_SECTIONS:
        body = markdown_section(text, title)
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        # `body` already opens with the section's own `# {title}` heading, so the
        # provenance note leads and the heading stands on its own (no duplicate H1).
        dst.write_text(
            "<!--\n"
            "Materialized from the consolidated USD Core Specification markdown\n"
            f"(core/{spec_version}/core_spec.md) in aousd/specifications-public.\n"
            f"Spec version: {spec_version}\n"
            f"Pinned ref: {pinned_ref}\n"
            "-->\n\n"
            f"{body}",
            encoding="utf-8",
            newline="\n",
        )
    write_pin_file(
        out_dir,
        [
            "source: specifications-public",
            "repo: aousd/specifications-public",
            f"spec_version: {spec_version}",
            f"tag_or_commit: {pinned_ref}",
            f"resolved_commit: {resolved_commit}",
            f"source_markdown: core/{spec_version}/core_spec.md",
        ],
    )


def copy_markdown_from_repo(
    source_repo: Path,
    worktree_dir: Path,
    out_dir: Path,
    commit: str,
    spec_version: str | None,
) -> None:
    if not source_repo.exists():
        raise MaterializeError(f"source repo not found: {source_repo}")

    resolved_commit, pinned_ref = resolve_pin(source_repo, commit)
    head = run_checked(["git", "-C", str(source_repo), "rev-parse", "HEAD"])

    # Only spin up a detached worktree when pinning a specific commit that differs
    # from the current checkout. The public repo has no tags, so the common path
    # resolves to HEAD and reads source_repo directly.
    if resolved_commit != head:
        if not worktree_dir.exists():
            worktree_dir.parent.mkdir(parents=True, exist_ok=True)
            run_checked(
                ["git", "-C", str(source_repo), "worktree", "add", "--detach",
                 str(worktree_dir), resolved_commit]
            )
        wt_head = run_checked(["git", "-C", str(worktree_dir), "rev-parse", "HEAD"])
        if wt_head != resolved_commit:
            raise MaterializeError(f"worktree {worktree_dir} is at {wt_head}, expected {resolved_commit}")
        read_root = worktree_dir
    else:
        read_root = source_repo

    # Preferred: the consolidated core/<version>/core_spec.md layout published today.
    spec_md, version = find_consolidated_spec(read_root, spec_version)
    if spec_md is not None:
        materialize_from_consolidated_markdown(spec_md, out_dir, version, pinned_ref, resolved_commit)
        return

    # Legacy: a checkout carrying per-section specification/<name>/README.md files.
    if all((read_root / rel).exists() for rel in PINNED_FILES):
        out_dir.mkdir(parents=True, exist_ok=True)
        for rel in PINNED_FILES:
            src = read_root / rel
            dst = out_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        write_pin_file(
            out_dir,
            [
                "source: specifications-public",
                "repo: aousd/specifications-public",
                f"tag_or_commit: {pinned_ref}",
                f"resolved_commit: {resolved_commit}",
                f"source_worktree: {read_root}",
            ],
        )
        return

    raise MaterializeError(
        f"source repo {read_root} has neither core/<version>/core_spec.md "
        "(current public layout) nor specification/<name>/README.md (legacy layout)."
    )


def write_pin_file(out_dir: Path, lines: Iterable[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines).rstrip() + "\n"
    (out_dir / "SPEC_PIN.txt").write_text(text, encoding="ascii", newline="\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", help="local aousd/specifications-public checkout")
    parser.add_argument("--commit", default=DEFAULT_COMMIT, help="spec tag or commit to pin")
    parser.add_argument(
        "--spec-version",
        default=DEFAULT_SPEC_VERSION,
        help="spec version directory to read from the consolidated public layout "
             "(core/<version>/core_spec.md); falls back to the latest published version",
    )
    parser.add_argument(
        "--worktree-dir",
        help="detached worktree directory for --source-repo; defaults under .spec-worktrees",
    )
    parser.add_argument("--out-dir", default=str(root / "spec" / "pinned"))
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = repo_root()
    out_dir = Path(args.out_dir).expanduser().resolve()
    source_repo = resolve_source_repo(args.source_repo)
    if source_repo is None:
        print(
            "materialize-spec: --source-repo or AOUSD_SPECIFICATIONS_PUBLIC_REPO "
            "is required.",
            file=sys.stderr,
        )
        return 2

    worktree_dir = (
        Path(args.worktree_dir).expanduser().resolve()
        if args.worktree_dir
        else default_worktree_dir(root, args.commit)
    )

    try:
        copy_markdown_from_repo(source_repo, worktree_dir, out_dir, args.commit, args.spec_version)
        print(f"Materialized pinned spec markdown into {out_dir}")
    except MaterializeError as exc:
        print(f"materialize-spec: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
