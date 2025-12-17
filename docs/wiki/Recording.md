# Recording

Vociferous uses a simple **press-to-toggle** recording mode.

## How It Works

1. **Press** the activation key (default: Alt) → recording starts
2. **Speak** into your microphone
3. **Press** the activation key again → recording stops and transcription begins

After transcription completes, the text is copied to your clipboard. Paste with Ctrl+V.

## Status Indicators

| Status | UI Display |
|--------|------------|
| Ready/Idle | Status text is blank |
| Recording | "Recording" |
| Transcribing | "Transcribing" |

## Voice Activity Detection

While recording, VAD (Voice Activity Detection) monitors your audio:
- Detects speech vs. silence
- Trims silence from the audio buffer
- Improves transcription quality

VAD does **not** automatically stop recording in the current version. You must press the activation key again to stop.

## Cancel Recording

To abort a recording without transcribing:
- Click the cancel button in the UI
- The status returns to blank (ready)

## Tips

- **Speak clearly** into a good microphone for best results
- **Short pauses** are fine - VAD handles natural speech patterns
- **Background noise** may affect accuracy; consider a noise-canceling mic
- **Recording length** is limited by available memory, but typical dictations (under 5 minutes) work well

## Known Limitations

- The default Alt hotkey currently captures **both** Alt keys, which may temporarily affect normal Alt-key usage in other applications
- A dedicated Start/Stop UI button is planned for a future release
