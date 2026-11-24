# Text to speech with the voices built into Windows (Windows.Media.SpeechSynthesis, the OneCore voices: Hebrew
# "Asaf", English "David" / "Zira" / "Mark" ...).  Used by trm4/guide_voice.py; no Python package is needed.
#
#   -Job <file.json>   UTF-8 JSON: {"lang": "he-IL", "rate": 1.0, "items": [{"text": "...", "out": "x.wav"}, ...]}
#                      every item is written to its .wav (through a .part file, so a reader never sees half a file)
#   -List              prints the installed voices, one "language|name" per line
param([string]$Job = "", [switch]$List)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq "AsTask" -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq "IAsyncOperation``1" })[0]
function Await($op, $type) {
    $task = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    $task.Result
}

$voices = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices
Add-Type -AssemblyName System.Speech
$desktop = (New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | Where-Object { $_.Enabled }
if ($List) {
    foreach ($v in $voices) { "{0}|{1}" -f $v.Language, $v.DisplayName }
    foreach ($v in $desktop) { "{0}|{1}" -f $v.VoiceInfo.Culture.Name, $v.VoiceInfo.Name }
    exit 0
}

$spec = [IO.File]::ReadAllText($Job, [Text.Encoding]::UTF8) | ConvertFrom-Json
$prefix = $spec.lang.Split("-")[0]
$voice = $voices | Where-Object { $_.Language -eq $spec.lang } | Select-Object -First 1
if ($null -eq $voice) { $voice = $voices | Where-Object { $_.Language.StartsWith($prefix) } | Select-Object -First 1 }
if ($null -eq $voice) {
    # no OneCore voice: the older desktop voices (System.Speech, SAPI)
    $dv = $desktop | Where-Object { $_.VoiceInfo.Culture.Name.StartsWith($prefix) } | Select-Object -First 1
    if ($null -eq $dv) { [Console]::Error.WriteLine("no voice for " + $spec.lang); exit 2 }
    $ss = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $ss.SelectVoice($dv.VoiceInfo.Name)
    $ss.Rate = [int][Math]::Max(-10, [Math]::Min(10, [Math]::Round(([double]$spec.rate - 1.0) * 10)))
    foreach ($item in $spec.items) {
        $part = $item.out + ".part"
        $ss.SetOutputToWaveFile($part)
        $ss.Speak([string]$item.text)
        $ss.SetOutputToNull()
        Move-Item -LiteralPath $part -Destination $item.out -Force
    }
    $ss.Dispose()
    exit 0
}
$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$synth.Voice = $voice
try { $synth.Options.SpeakingRate = [double]$spec.rate } catch { }
foreach ($item in $spec.items) {
    $stream = Await ($synth.SynthesizeTextToStreamAsync([string]$item.text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
    $reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
    $n = Await ($reader.LoadAsync([uint32]$stream.Size)) ([uint32])
    $bytes = New-Object byte[] $n
    $reader.ReadBytes($bytes)
    $part = $item.out + ".part"
    [IO.File]::WriteAllBytes($part, $bytes)
    Move-Item -LiteralPath $part -Destination $item.out -Force
    $reader.Dispose(); $stream.Dispose()
}
