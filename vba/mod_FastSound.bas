Attribute VB_Name = "mod_FastSound"
' ============================================================================
'  mod_FastSound  -  low-latency sound playback for Wheel of Fortune
'
'  Replaces the slow  Shapes(...).ActionSettings(ppMouseClick).SoundEffect.Play
'  mechanism (which re-initializes PowerPoint's sound subsystem and re-reads the
'  embedded sound on every call) with the Win32 MCI API.
'
'  - All 8 embedded WAVs are extracted from the .pptm to %TEMP%\wof_sounds\ once
'    per session and pre-opened as named MCI devices, so "play <alias> from 0"
'    is effectively instant.
'  - Each sound is its own MCI device, so background music and short letter SFX
'    OVERLAP instead of cutting each other off.
'  - If MCI is unavailable (Mac PowerPoint, extraction failure, etc.) PlaySnd
'    falls back to the original SoundEffect.Play, so nothing breaks.
'
'  Usage: replace each
'     ActivePresentation.Slides(11).Shapes("X").ActionSettings(ppMouseClick).SoundEffect.Play
'  with
'     PlaySnd "X"
'  for the 8 shapes handled below. Leave TossUpMusic / FinalSpinMusic on the
'  original call (they have no embedded WAV and are user-customizable).
' ============================================================================
Option Explicit

#If VBA7 Then
    Private Declare PtrSafe Function mciSendString Lib "winmm.dll" Alias "mciSendStringA" ( _
        ByVal lpstrCommand As String, ByVal lpstrReturnString As String, _
        ByVal uReturnLength As Long, ByVal hwndCallback As LongPtr) As Long
#Else
    Private Declare Function mciSendString Lib "winmm.dll" Alias "mciSendStringA" ( _
        ByVal lpstrCommand As String, ByVal lpstrReturnString As String, _
        ByVal uReturnLength As Long, ByVal hwndCallback As Long) As Long
#End If

Private Const SND_DIR As String = "wof_sounds"
Private gSoundReady As Boolean
Private gSoundTried As Boolean

' Public entry point used by every converted call site.
Public Sub PlaySnd(ByVal shapeName As String)
    On Error Resume Next
    If Not gSoundTried Then
        InitFastSound
        gSoundTried = True
    End If
    If gSoundReady Then
        If mciSendString("play " & shapeName & " from 0", vbNullString, 0, 0&) = 0 Then Exit Sub
    End If
    ' Fallback: original PowerPoint behavior (Mac / macros just loaded / open failed)
    ActivePresentation.Slides(11).Shapes(shapeName).ActionSettings(ppMouseClick).SoundEffect.Play
End Sub

' Extract embedded WAVs once, then pre-open one MCI device per sound.
' Idempotent: safe to call from every Puzzle Board entry point and on every visit.
Public Sub InitFastSound()
    On Error GoTo fail
    If gSoundReady Then Exit Sub

    ' MCI devices persist in Windows audio even if VBA module-level variables reset
    ' (e.g. an unhandled error in any other macro resets module state).
    ' Check the first device before doing full extraction + open.
    Dim retBuf As String: retBuf = Space(32)
    If mciSendString("status GuessLetterCorrect mode", retBuf, Len(retBuf), 0&) = 0 Then
        gSoundReady = True
        Exit Sub
    End If

    Dim destDir As String
    destDir = ExtractSounds()
    If destDir = "" Then GoTo fail

    Dim names As Variant, i As Long, wav As String
    names = Array("GuessLetterCorrect", "LoadPuzzleChime", "GuessLetterWrong", _
                  "SpinWheel", "FinalSpinAlert", "BonusCountdown", _
                  "SolvePuzzleChime", "TripleTossUpSolve")
    For i = LBound(names) To UBound(names)
        wav = destDir & "\" & MediaFor(CStr(names(i)))
        If Dir(wav) <> "" Then
            mciSendString "close " & names(i), vbNullString, 0, 0&     ' idempotent
            mciSendString "open """ & wav & """ type waveaudio alias " & names(i), vbNullString, 0, 0&
        End If
    Next i
    gSoundReady = True
    Exit Sub
fail:
    gSoundReady = False
End Sub

' Shape name -> embedded media file (verified against ppt/slides/_rels/slide11.xml.rels).
Private Function MediaFor(ByVal shapeName As String) As String
    Select Case shapeName
        Case "GuessLetterCorrect": MediaFor = "audio1.wav"
        Case "LoadPuzzleChime":    MediaFor = "audio2.wav"
        Case "GuessLetterWrong":   MediaFor = "audio3.wav"
        Case "SpinWheel":          MediaFor = "audio4.wav"
        Case "FinalSpinAlert":     MediaFor = "audio5.wav"
        Case "BonusCountdown":     MediaFor = "audio6.wav"
        Case "SolvePuzzleChime":   MediaFor = "audio7.wav"
        Case "TripleTossUpSolve":  MediaFor = "audio8.wav"
        Case Else:                 MediaFor = ""
    End Select
End Function

' Returns True if MCI devices are open and ready — call from VBE Immediate window
' to diagnose:  ? mod_FastSound.FastSoundReady()
Public Function FastSoundReady() As Boolean
    FastSoundReady = gSoundReady
End Function

' Extract ppt\media\*.wav from the live .pptm to %TEMP%\wof_sounds\.
' Uses Shell.Application zip namespace: pass each FolderItem to sh.Namespace() to
' navigate into zip subfolders — using .GetFolder on a zip FolderItem returns Nothing.
Private Function ExtractSounds() As String
    On Error GoTo fail
    Dim tmp As String, zipPath As String, destDir As String
    tmp = Environ$("TEMP")
    destDir = tmp & "\" & SND_DIR
    If Dir(destDir, vbDirectory) = "" Then MkDir destDir
    If Dir(destDir & "\audio8.wav") <> "" Then         ' already extracted this session
        ExtractSounds = destDir
        Exit Function
    End If

    zipPath = tmp & "\wof_audio.zip"
    If Dir(zipPath) <> "" Then Kill zipPath
    FileCopy ActivePresentation.FullName, zipPath       ' read-copy of the live deck

    Dim sh As Object, pptNS As Object, mediaNS As Object, dest As Object, it As Object
    Set sh = CreateObject("Shell.Application")
    Set pptNS = sh.Namespace(sh.Namespace(zipPath).ParseName("ppt"))
    Set mediaNS = sh.Namespace(pptNS.ParseName("media"))
    Set dest = sh.Namespace(destDir)
    For Each it In mediaNS.Items
        If LCase$(Right$(it.Name, 4)) = ".wav" Then
            dest.CopyHere it, &H4 Or &H10 Or &H200 Or &H400
        End If
    Next it

    Dim t As Single: t = Timer                          ' CopyHere is async; wait for completion
    Do While Dir(destDir & "\audio8.wav") = "" And Timer < t + 5
        DoEvents
    Loop
    If Dir(destDir & "\audio8.wav") <> "" Then ExtractSounds = destDir
    Exit Function
fail:
    ExtractSounds = ""
End Function
