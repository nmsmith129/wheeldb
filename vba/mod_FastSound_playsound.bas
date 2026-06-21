Attribute VB_Name = "mod_FastSound"
' ============================================================================
'  mod_FastSound  -  low-latency sound playback for Wheel of Fortune
'                    (PlaySound variant - experimental, wof001 only)
'
'  Drop-in replacement for the MCI version of mod_FastSound. Keeps the same
'  public API (PlaySnd / InitFastSound / FastSoundReady) and the same
'  %TEMP%\wof_sounds\ extraction, but plays each WAV with the Win32 PlaySound
'  API instead of opening one MCI device per sound.
'
'  Tradeoff vs the MCI version:
'    - SIMPLER: no per-sound MCI device to open/close, no MCI re-entry guard.
'    - BUT PlaySound has a single async playback channel per process, so each
'      new PlaySnd call STOPS the previous one. Sounds no longer OVERLAP the
'      way the MCI version allowed. Background music left on the original
'      SoundEffect.Play path is unaffected (it does not go through PlaySnd).
'
'  If PlaySound is unavailable or the WAV is missing, PlaySnd falls back to the
'  original SoundEffect.Play, so nothing breaks.
' ============================================================================
Option Explicit

#If VBA7 Then
    Private Declare PtrSafe Function PlaySound Lib "winmm.dll" Alias "PlaySoundA" ( _
        ByVal lpszName As String, ByVal hModule As LongPtr, ByVal dwFlags As Long) As Long
    ' mciSendString is used ONLY for the silent keep-alive loop below, never for SFX.
    Private Declare PtrSafe Function mciSendString Lib "winmm.dll" Alias "mciSendStringA" ( _
        ByVal lpstrCommand As String, ByVal lpstrReturnString As String, _
        ByVal uReturnLength As Long, ByVal hwndCallback As LongPtr) As Long
#Else
    Private Declare Function PlaySound Lib "winmm.dll" Alias "PlaySoundA" ( _
        ByVal lpszName As String, ByVal hModule As Long, ByVal dwFlags As Long) As Long
    Private Declare Function mciSendString Lib "winmm.dll" Alias "mciSendStringA" ( _
        ByVal lpstrCommand As String, ByVal lpstrReturnString As String, _
        ByVal uReturnLength As Long, ByVal hwndCallback As Long) As Long
#End If

Private Const SND_ASYNC As Long = &H1        ' play asynchronously (return immediately)
Private Const SND_NODEFAULT As Long = &H2    ' do NOT play the system default sound on failure
Private Const SND_FILENAME As Long = &H20000 ' lpszName is a file path

Private Const SND_DIR As String = "wof_sounds"
Private Const KEEPALIVE_ALIAS As String = "wofKeepAlive"
Private Const KEEPALIVE_SECONDS As Long = 30   ' length of the looped silence clip
Private gSoundReady As Boolean
Private gSoundTried As Boolean
Private gSndDir As String

' Public entry point used by every converted call site.
Public Sub PlaySnd(ByVal shapeName As String)
    On Error Resume Next
    If Not gSoundTried Then
        InitFastSound
        gSoundTried = True
    End If
    If gSoundReady Then
        Dim wav As String
        wav = gSndDir & "\" & MediaFor(shapeName)
        If MediaFor(shapeName) <> "" Then
            If Dir(wav) <> "" Then
                If PlaySound(wav, 0, SND_FILENAME Or SND_ASYNC Or SND_NODEFAULT) <> 0 Then Exit Sub
            End If
        End If
    End If
    ' Fallback: original PowerPoint behavior (Mac / extraction failed / file missing)
    ActivePresentation.Slides(11).Shapes(shapeName).ActionSettings(ppMouseClick).SoundEffect.Play
End Sub

' Extract embedded WAVs once per session. Idempotent: safe to call from every
' Puzzle Board entry point and on every visit.
Public Sub InitFastSound()
    On Error GoTo fail
    StartKeepAlive                  ' keep the audio endpoint warm (idempotent, independent of extraction)
    If gSoundReady Then Exit Sub

    Dim destDir As String
    destDir = ExtractSounds()
    If destDir = "" Then GoTo fail

    gSndDir = destDir
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

' Returns True if the WAVs are extracted and ready — call from VBE Immediate window
' to diagnose:  ? mod_FastSound.FastSoundReady()
Public Function FastSoundReady() As Boolean
    FastSoundReady = gSoundReady
End Function

' ----------------------------------------------------------------------------
'  Keep-alive: hold the audio endpoint active so it never drops to a low-power
'  idle state. When the endpoint idles, the FIRST PlaySound after silence pays a
'  device wake-up penalty (audible lag). We avoid this by continuously looping an
'  inaudible silent WAV on its OWN MCI device, separate from the PlaySound SFX
'  channel, so the two mix at the endpoint and the device stays warm.
'  Idempotent: re-arming when already playing is a single cheap status query.
' ----------------------------------------------------------------------------
Public Sub StartKeepAlive()
    On Error Resume Next
    ' Already looping? Leave it. (MCI devices persist even if VBA module state resets.)
    Dim retBuf As String: retBuf = Space$(64)
    If mciSendString("status " & KEEPALIVE_ALIAS & " mode", retBuf, Len(retBuf), 0&) = 0 Then
        If InStr(1, retBuf, "playing", vbTextCompare) > 0 Then Exit Sub
        mciSendString "close " & KEEPALIVE_ALIAS, vbNullString, 0, 0&   ' stopped/paused: reopen
    End If

    Dim tmp As String, sil As String
    tmp = Environ$("TEMP")
    If Dir(tmp & "\" & SND_DIR, vbDirectory) = "" Then MkDir tmp & "\" & SND_DIR
    sil = tmp & "\" & SND_DIR & "\silence.wav"
    If Dir(sil) = "" Then CreateSilenceWav sil, KEEPALIVE_SECONDS
    If Dir(sil) = "" Then Exit Sub

    If mciSendString("open """ & sil & """ type waveaudio alias " & KEEPALIVE_ALIAS, vbNullString, 0, 0&) = 0 Then
        ' "repeat" loops the clip continuously, so the endpoint never goes idle.
        mciSendString "play " & KEEPALIVE_ALIAS & " repeat", vbNullString, 0, 0&
    End If
End Sub

' Stop and release the keep-alive device. Optional — call from the Immediate
' window if you want to confirm idle-lag returns without it.
Public Sub StopKeepAlive()
    On Error Resume Next
    mciSendString "close " & KEEPALIVE_ALIAS, vbNullString, 0, 0&
End Sub

' Write a PCM WAV of pure silence (8-bit mono, 8 kHz) if it doesn't exist.
' 8-bit silence is the 0x80 midpoint, so loop boundaries are seamless/inaudible.
Private Sub CreateSilenceWav(ByVal path As String, ByVal seconds As Long)
    On Error GoTo done
    Const RATE As Long = 8000
    Dim dataSize As Long: dataSize = RATE * seconds      ' 8-bit mono => 1 byte/sample
    Dim total As Long: total = 44 + dataSize
    Dim b() As Byte: ReDim b(0 To total - 1)
    Dim p As Long: p = 0
    WriteStr b, p, "RIFF"
    WriteLong b, p, 36 + dataSize
    WriteStr b, p, "WAVE"
    WriteStr b, p, "fmt "
    WriteLong b, p, 16            ' fmt chunk size
    WriteWord b, p, 1            ' PCM
    WriteWord b, p, 1            ' channels = mono
    WriteLong b, p, RATE          ' sample rate
    WriteLong b, p, RATE          ' byte rate (blockAlign = 1)
    WriteWord b, p, 1            ' block align
    WriteWord b, p, 8            ' bits per sample
    WriteStr b, p, "data"
    WriteLong b, p, dataSize
    Dim i As Long
    For i = p To total - 1
        b(i) = &H80              ' 8-bit PCM silence midpoint
    Next i
    Dim fn As Integer: fn = FreeFile
    Open path For Binary Access Write As #fn
    Put #fn, 1, b
    Close #fn
done:
End Sub

Private Sub WriteStr(ByRef b() As Byte, ByRef p As Long, ByVal s As String)
    Dim i As Long
    For i = 1 To Len(s)
        b(p) = Asc(Mid$(s, i, 1)): p = p + 1
    Next i
End Sub

Private Sub WriteLong(ByRef b() As Byte, ByRef p As Long, ByVal v As Long)
    b(p) = v And &HFF: p = p + 1
    b(p) = (v \ &H100) And &HFF: p = p + 1
    b(p) = (v \ &H10000) And &HFF: p = p + 1
    b(p) = (v \ &H1000000) And &HFF: p = p + 1
End Sub

Private Sub WriteWord(ByRef b() As Byte, ByRef p As Long, ByVal v As Long)
    b(p) = v And &HFF: p = p + 1
    b(p) = (v \ &H100) And &HFF: p = p + 1
End Sub

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
