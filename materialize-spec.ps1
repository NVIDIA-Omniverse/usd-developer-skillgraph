# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

param(
    [string]$SourceRepo = "",
    [string]$Commit = "v1.0.1",
    [string]$SpecVersion = "1.0.1",
    [string]$WorktreeDir = "",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "materialize-spec.py"

if (-not (Test-Path $pythonScript)) {
    throw "Python materializer not found: $pythonScript"
}

$python = $env:PYTHON
if ([string]::IsNullOrWhiteSpace($python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $python = "py"
    } else {
        $python = "python3"
    }
}

$pythonArgs = @($pythonScript, "--commit", $Commit)

if (-not [string]::IsNullOrWhiteSpace($SpecVersion)) {
    $pythonArgs += @("--spec-version", $SpecVersion)
}

if (-not [string]::IsNullOrWhiteSpace($SourceRepo)) {
    $pythonArgs += @("--source-repo", $SourceRepo)
}

if (-not [string]::IsNullOrWhiteSpace($WorktreeDir)) {
    $pythonArgs += @("--worktree-dir", $WorktreeDir)
}

if (-not [string]::IsNullOrWhiteSpace($OutDir)) {
    $pythonArgs += @("--out-dir", $OutDir)
}

& $python @pythonArgs
if ($LASTEXITCODE -ne 0) {
    throw "materialize-spec.py failed with exit code $LASTEXITCODE"
}
