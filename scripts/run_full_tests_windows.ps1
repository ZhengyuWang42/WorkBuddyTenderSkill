<#
.SYNOPSIS
    Run the complete test suite on a Windows host with restrictive directory ACLs.

.DESCRIPTION
    Environment compatibility helper - not product code and not a test.

    On this Windows host `pathlib.Path.mkdir(mode=0o700)` - the mode pytest's
    temporary-directory factory uses for every `tmp_path` - produces a directory
    the creating process cannot enumerate (`PermissionError [WinError 5]`).
    pytest scans that directory while handing out the first `tmp_path` and again
    at session finish, so every `tmp_path` test errors and the session exits
    non-zero even when the code under test is fine.

    This script performs exactly the two documented steps for such a host:

      1. a fresh, writable `--basetemp` directory (nothing stale, no ACL reuse);
      2. the optional compatibility plugin `scripts/dev/pytest_fscompat.py`,
         loaded explicitly through `PYTEST_PLUGINS` for this run only.

    Ordinary environments need none of this: run `pytest -q` with a writable
    basetemp.  This script only exists so the Windows evidence is reproducible.
    It changes no test, no assertion and no product module, and it never touches
    repository-wide ACLs.

.PARAMETER Out
    Evidence file to persist the run to.  Defaults to the Round-4 closure8 name.

.PARAMETER Paths
    Test paths to run.  Defaults to the whole `tests` directory.

.EXAMPLE
    pwsh -NoProfile -File scripts/run_full_tests_windows.ps1
#>
[CmdletBinding()]
param(
    [string]$Out = 'acceptance/reports/v1_generalization/full_test_suite_windowshost.txt',
    [string]$BasetempRoot = 'acceptance/workspace',
    [string[]]$Paths = @('tests')
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$python = Join-Path $repo '.venv/Scripts/python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

$stamp = [guid]::NewGuid().ToString('N')
$basetemp = Join-Path $repo "$BasetempRoot/pytest_fullsuite_$stamp"
$junit = Join-Path $repo "$BasetempRoot/_scratch_round4_vii/fullsuite_$stamp.xml"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $junit) | Out-Null

# 1) the optional Windows ACL compatibility plugin, for this run only
$env:PYTHONPATH = (Join-Path $repo 'scripts/dev')
$env:PYTEST_PLUGINS = 'pytest_fscompat'

# 2) a fresh writable basetemp
Write-Host "basetemp : $basetemp"
Write-Host "plugin   : scripts/dev/pytest_fscompat.py"

$console = Join-Path ([System.IO.Path]::GetTempPath()) "pytest_console_$stamp.txt"
& $python -X utf8 -m pytest -q -p no:cacheprovider --basetemp $basetemp --junitxml $junit @Paths *> $console
$exit = $LASTEXITCODE

# pytest's own final count line is not reliably capturable through PowerShell on
# this host, so the counts are read from the run's JUnit XML record instead.
$counts = [ordered]@{ tests = 0; failures = 0; errors = 0; skipped = 0; time = '0' }
if (Test-Path $junit) {
    [xml]$xml = Get-Content $junit -Raw
    $suite = $xml.testsuites.testsuite
    if (-not $suite) { $suite = $xml.testsuite }
    $counts.tests = [int]$suite.tests
    $counts.failures = [int]$suite.failures
    $counts.errors = [int]$suite.errors
    $counts.skipped = [int]$suite.skipped
    $counts.time = [string]$suite.time
}
$passed = $counts.tests - $counts.failures - $counts.errors - $counts.skipped

$header = @(
    '# full test suite (Windows ACL compatibility path)',
    "# command  : .venv/Scripts/python.exe -X utf8 -m pytest -q -p no:cacheprovider --basetemp $basetemp --junitxml $junit",
    '# host note: PYTEST_PLUGINS=pytest_fscompat (scripts/dev/pytest_fscompat.py)',
    '#            Path.mkdir(mode=0o700) is relaxed to the default mode because this',
    '#            host cannot enumerate a directory created with mode 0o700; the plugin',
    '#            changes no assertion, no test and no product module.',
    "# result   : $passed passed, $($counts.skipped) skipped, $($counts.failures) failed, $($counts.errors) errors",
    "# junitxml : tests=$($counts.tests) failures=$($counts.failures) errors=$($counts.errors) skipped=$($counts.skipped) time=$($counts.time)s",
    "# exit code: $exit",
    '',
    ''
)
$body = if (Test-Path $console) { Get-Content $console -Raw } else { '' }
$outPath = Join-Path $repo $Out
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outPath) | Out-Null
Set-Content -Path $outPath -Value (($header -join "`n") + $body) -Encoding utf8

Write-Host "PASSED=$passed SKIPPED=$($counts.skipped) FAILED=$($counts.failures) ERRORS=$($counts.errors) EXIT=$exit"
Write-Host "evidence : $Out"
if ($exit -ne 0) { exit $exit }
