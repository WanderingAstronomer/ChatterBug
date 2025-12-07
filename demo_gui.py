#!/usr/bin/env python
"""Demo script to showcase Luciferous GUI features.

This script demonstrates the key components without actually launching the GUI,
useful for testing and documentation.
"""

from pathlib import Path


def demo_installation_modes():
    """Demonstrate installation mode handling."""
    from vociferous.gui.installer import InstallMode, DependencyInstaller
    
    print("=== Installation Modes ===")
    print(f"GPU Mode: {InstallMode.GPU}")
    print(f"CPU Mode: {InstallMode.CPU}")
    print(f"Both Mode: {InstallMode.BOTH}")
    
    installer = DependencyInstaller()
    status = installer.check_installation_status()
    print(f"\nCurrent Installation Status:")
    print(f"  PyTorch installed: {status['torch']}")
    print(f"  CUDA available: {status['cuda']}")


def demo_transcription_task():
    """Demonstrate transcription task creation."""
    from vociferous.gui.transcription import TranscriptionTask, GUITranscriptionManager
    
    print("\n=== Transcription Task ===")
    
    # Create a mock file path
    test_file = Path("/tmp/test_audio.wav")
    
    # Progress callback
    def on_progress(text: str):
        print(f"Progress: {text[:50]}...")
    
    # Completion callback
    def on_complete(text: str):
        print(f"Complete! Length: {len(text)} chars")
    
    # Error callback
    def on_error(error: str):
        print(f"Error: {error}")
    
    # Create task
    task = TranscriptionTask(
        file_path=test_file,
        engine="whisper_turbo",
        language="en",
        on_progress=on_progress,
        on_complete=on_complete,
        on_error=on_error,
    )
    
    print(f"Created task for: {task.file_path}")
    print(f"Engine: {task.engine}")
    print(f"Language: {task.language}")
    print(f"Running: {task.is_running}")
    
    # Create manager
    manager = GUITranscriptionManager()
    print(f"\nManager created, current task: {manager.current_task}")


def demo_config_operations():
    """Demonstrate configuration loading and saving."""
    from vociferous.config import load_config, save_config
    
    print("\n=== Configuration Operations ===")
    
    # Load config
    config = load_config()
    print(f"Config loaded:")
    print(f"  Engine: {config.engine}")
    print(f"  Device: {config.device}")
    print(f"  Model: {config.model_name}")
    print(f"  Compute Type: {config.compute_type}")
    
    # Show config file location
    config_path = Path.home() / ".config" / "vociferous" / "config.toml"
    print(f"\nConfig file: {config_path}")
    print(f"Exists: {config_path.exists()}")
    
    # Note: We don't actually save to avoid modifying user's config
    print("\nNote: save_config(config) would persist changes to config.toml")


def demo_first_run_detection():
    """Demonstrate first-run detection."""
    from pathlib import Path
    
    print("\n=== First Run Detection ===")
    
    marker_file = Path.home() / ".config" / "vociferous" / ".gui_setup_complete"
    is_first_run = not marker_file.exists()
    
    print(f"Marker file: {marker_file}")
    print(f"Is first run: {is_first_run}")
    
    if is_first_run:
        print("\nOn first run, the splash screen will:")
        print("  1. Welcome the user")
        print("  2. Ask for hardware selection (GPU/CPU/Both)")
        print("  3. Install dependencies")
        print("  4. Create the marker file")
        print("  5. Navigate to main app")
    else:
        print("\nNot first run, will skip splash screen")


def demo_gui_structure():
    """Demonstrate GUI structure without launching."""
    print("\n=== GUI Structure ===")
    print("""
LuciferousApp (KivyMD App)
├── Theme: Dark with Blue accents
├── Window: 1200x800 (minimum 800x600)
└── Layout: NavigationLayout
    ├── Navigation Drawer (left, vertical)
    │   ├── Home
    │   └── Settings
    └── Content Area
        ├── Top App Bar (bright blue #1A5FBF)
        └── Screen Manager
            ├── HomeScreen
            │   ├── File selection card
            │   ├── Browse button
            │   ├── Transcribe button
            │   └── Output display
            └── SettingsScreen
                ├── Engine configuration
                │   ├── Engine dropdown
                │   ├── Model selection
                │   └── Device selection
                ├── Transcription options
                │   ├── VAD toggle
                │   ├── Batching toggle
                │   └── Word timestamps
                └── Save button
    """)


def demo_supported_formats():
    """List supported audio formats."""
    print("\n=== Supported Audio Formats ===")
    formats = [
        ('.wav', 'Waveform Audio File'),
        ('.mp3', 'MPEG Audio Layer 3'),
        ('.flac', 'Free Lossless Audio Codec'),
        ('.m4a', 'MPEG-4 Audio'),
        ('.ogg', 'Ogg Vorbis'),
        ('.opus', 'Opus Audio'),
        ('.aac', 'Advanced Audio Coding'),
        ('.wma', 'Windows Media Audio'),
    ]
    
    for ext, name in formats:
        print(f"  {ext:8} - {name}")


def main():
    """Run all demonstrations."""
    print("=" * 60)
    print("Luciferous GUI Demonstration")
    print("=" * 60)
    
    try:
        demo_installation_modes()
    except Exception as e:
        print(f"Installation modes demo error: {e}")
    
    try:
        demo_transcription_task()
    except Exception as e:
        print(f"Transcription task demo error: {e}")
    
    try:
        demo_config_operations()
    except Exception as e:
        print(f"Config operations demo error: {e}")
    
    try:
        demo_first_run_detection()
    except Exception as e:
        print(f"First run detection demo error: {e}")
    
    demo_gui_structure()
    demo_supported_formats()
    
    print("\n" + "=" * 60)
    print("To launch the actual GUI, run:")
    print("  luciferous")
    print("Or:")
    print("  python -m vociferous.gui.app")
    print("=" * 60)


if __name__ == "__main__":
    main()
