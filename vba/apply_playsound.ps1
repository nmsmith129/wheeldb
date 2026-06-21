# apply_playsound.ps1
# Swaps the experimental PlaySound variant of mod_FastSound into a Wheel of
# Fortune .pptm (defaults to games\wof001.pptm, for testing):
#   1. removes the existing mod_FastSound (MCI) component and imports the
#      PlaySound variant (same VB_Name = "mod_FastSound", drop-in replacement)
#   2. rewrites the 8 SoundEffect.Play call sites in Module1 to PlaySnd "<shape>"
#      (idempotent - no-op if the MCI version already rewired them)
#   3. inserts InitFastSound into the two Puzzle Board entry subs (idempotent)
#   4. saves the file
#
# Requires "Trust access to the VBA project object model" (AccessVBOM=1) and the
# target .pptm to be CLOSED in PowerPoint.
# Run:  pwsh -File vba\apply_playsound.ps1            # -> games\wof001.pptm
#       pwsh -File vba\apply_playsound.ps1 -File "games\wofNNN.pptm"
param(
    [string]$File = (Join-Path $PSScriptRoot '..\games\wof001.pptm'),
    [string]$Bas  = (Join-Path $PSScriptRoot 'mod_FastSound_playsound.bas')
)

$ErrorActionPreference = 'Stop'
$File = (Resolve-Path $File).Path
$Bas  = (Resolve-Path $Bas).Path

$shapes = @('GuessLetterCorrect','LoadPuzzleChime','GuessLetterWrong','SpinWheel',
            'FinalSpinAlert','BonusCountdown','SolvePuzzleChime','TripleTossUpSolve')
$boardSubs = @('goToPuzzleBoard','goToPuzzleBoardFromSetUpPuzzles')

$ppt = New-Object -ComObject PowerPoint.Application
try {
    # ReadOnly=$false, Untitled=$false, WithWindow=$false
    $pres = $ppt.Presentations.Open($File, $false, $false, $false)
    $proj = $pres.VBProject

    # (re)import the PlaySound module, replacing any existing mod_FastSound
    foreach ($c in @($proj.VBComponents)) {
        if ($c.Name -eq 'mod_FastSound') { $proj.VBComponents.Remove($c) }
    }
    $proj.VBComponents.Import($Bas) | Out-Null

    $cm = ($proj.VBComponents | Where-Object { $_.Name -eq 'Module1' }).CodeModule

    # 1) swap the 8 SoundEffect.Play call sites (idempotent)
    $text = $cm.Lines(1, $cm.CountOfLines)
    $before = $text
    foreach ($s in $shapes) {
        $find = 'ActivePresentation.Slides(11).Shapes("' + $s + '").ActionSettings(ppMouseClick).SoundEffect.Play'
        $repl = 'PlaySnd "' + $s + '"'
        $text = $text.Replace($find, $repl)
    }
    if ($text -ne $before) {
        $cm.DeleteLines(1, $cm.CountOfLines)
        $cm.InsertLines(1, $text)
    }

    # 2) insert InitFastSound before "View.GotoSlide 2" inside the two board subs (idempotent)
    foreach ($sub in $boardSubs) {
        $start = $cm.ProcStartLine($sub, 0)      # 0 = vbext_pk_Proc
        $count = $cm.ProcCountLines($sub, 0)
        for ($i = $start; $i -lt ($start + $count); $i++) {
            $line = $cm.Lines($i, 1)
            if ($line -match 'View\.GotoSlide 2\s*$' -and $line -notmatch 'InitFastSound') {
                if ($cm.Lines($i - 1, 1) -notmatch 'InitFastSound') {
                    $cm.InsertLines($i, '    InitFastSound')
                }
                break
            }
        }
    }

    $pres.Save()
    $pres.Close()
    Write-Host "Applied PlaySound mod_FastSound to $File"
}
finally {
    $ppt.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
    [System.GC]::Collect(); [System.GC]::WaitForPendingFinalizers()
}
