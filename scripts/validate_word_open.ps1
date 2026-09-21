[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
    [string[]] $Path
)

Set-StrictMode -Version Latest
$platformIsWindows = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
if (-not $platformIsWindows) {
    Write-Output "WORD_NORMAL_OPEN=SKIP_NON_WINDOWS"
    exit 0
}

$word = $null
$failed = $false
$opened = @()
try {
    try {
        $word = New-Object -ComObject Word.Application
    }
    catch {
        Write-Output ("WORD_NORMAL_OPEN=FAIL_COM_ACTIVATION " + $_.Exception.Message)
        exit 1
    }
    $word.Visible = $false
    $word.DisplayAlerts = 0

    foreach ($candidate in $Path) {
        $document = $null
        try {
            $resolved = (Resolve-Path -LiteralPath $candidate -ErrorAction Stop).Path
            # This is the normal Documents.Open path.  OpenAndRepair is not
            # requested and is intentionally not treated as acceptance.
            $document = $word.Documents.Open($resolved, $false, $true, $false)
            $opened += $resolved
            Write-Output ("WORD_NORMAL_OPEN=PASS " + $resolved)
        }
        catch {
            $failed = $true
            Write-Output ("WORD_NORMAL_OPEN=FAIL " + $candidate + " :: " + $_.Exception.Message)
        }
        finally {
            if ($null -ne $document) {
                try { $document.Close($false) } catch {}
                try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) } catch {}
            }
        }
    }
}
finally {
    if ($null -ne $word) {
        try { $word.Quit($false) } catch {}
        try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

if ($failed -or $opened.Count -ne $Path.Count) {
    exit 1
}
exit 0
