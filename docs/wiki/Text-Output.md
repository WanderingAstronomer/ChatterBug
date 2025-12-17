# Text Output

After transcription, text is copied to the clipboard for pasting into any application.

## Workflow

```
Transcription Complete
         │
         ▼
Copy to Clipboard
         │
         ▼
User pastes with Ctrl+V
```

## Clipboard Methods

### pyperclip (Primary)

```python
import pyperclip
pyperclip.copy(text)
```

Cross-platform clipboard access. Works on most systems with appropriate backends (xclip, xsel, wl-copy).

### wl-copy (Wayland Fallback)

```python
subprocess.run(["wl-copy"], input=text, text=True)
```

Direct Wayland clipboard access when pyperclip is unavailable.

## Why Clipboard?

### Wayland Security Model

Wayland restricts applications from:
- Simulating keystrokes to other applications
- Injecting text into other windows
- Accessing other applications' input focus

### Clipboard Advantages

- **Universal**: Works across all toolkits (Qt, GTK, Electron, terminal)
- **No permissions**: No special setup or group membership required for output
- **User control**: You decide when and where to paste
- **Predictable**: Same behavior everywhere

## Post-Processing

Before copying to clipboard, the transcription receives light post-processing:
- Leading/trailing whitespace is trimmed
- A trailing space is appended (current default behavior)

## Usage Patterns

### Quick Dictation

1. Focus target application (email, document, chat)
2. Press activation key, speak, press again
3. Ctrl+V to paste

### Editing Before Paste

1. Dictate into Vociferous
2. Review/edit in the main window's transcription panel
3. Click "Copy" to update clipboard with edited text
4. Paste into target application

## Troubleshooting

### Clipboard Empty

- Ensure `wl-clipboard` is installed (Wayland): `sudo apt install wl-clipboard`
- Check if pyperclip has a working backend

### Wrong Content Pasted

- Another application may have overwritten the clipboard
- Paste immediately after transcription completes
