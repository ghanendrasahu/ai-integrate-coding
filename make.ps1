#!/usr/bin/env pwsh
# PowerShell shortcuts mirroring the Makefile, so no `make` is required on Windows.
#
#   .\Make.ps1 up                    # start the web frontend at http://localhost:5000
#   .\Make.ps1 cli "build a REST API"  # run a task via the containerized agent
#   .\Make.ps1 logs                # tail the frontend logs
#   .\Make.ps1 down               # stop everything
#   .\Make.ps1 build              # rebuild the image
#   .\Make.ps1 shell              # open a shell in the agent container
#   .\Make.ps1 setup              # .venv + deps + Playwright Chromium (local)
#   .\Make.ps1 test               # full test suite (local)
#   .\Make.ps1 lint               # pyright type-check (local)
#   .\Make.ps1 clean              # remove Python caches (local)
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest = @()
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = "python"
if (Test-Path ".venv\Scripts\python.exe") { $Py = ".venv\Scripts\python.exe" }

switch ($Command) {
    "up"    { docker compose up --build; break }
    "down"  { docker compose down; break }
    "build" { docker compose build; break }
    "logs"  { docker compose logs -f; break }
    "shell" { docker compose run --rm --entrypoint bash cli; break }
    "cli"   { docker compose run --rm cli $Rest; break }
    "setup" {
        python -m venv .venv
        & $Py -m pip install --upgrade pip
        & $Py -m pip install -r requirements-dev.txt
        & $Py -m playwright install chromium
        break
    }
    "test"  { & $Py -m pytest tests frontend/tests -q; break }
    "lint"  { & $Py -m pyright; break }
    "clean" {
        Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force ".pytest_cache", ".mypy_cache", ".ruff_cache" -ErrorAction SilentlyContinue
        break
    }
    default {
        Write-Host "Usage: .\make.ps1 <command> [args]"
        Write-Host "  up | down | build | logs | shell | cli '<task>' | setup | test | lint | clean"
    }
}