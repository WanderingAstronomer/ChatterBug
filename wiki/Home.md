# Welcome to Vociferous

**Vociferous** is a local-first Automatic Speech Recognition (ASR) tool that transforms audio into text using state-of-the-art models while keeping all processing on your device.

## What is Vociferous?

Vociferous provides fast, accurate, and privacy-preserving speech-to-text transcription powered by:
- **Whisper large-v3-turbo** (via faster-whisper/CTranslate2) as the default engine
- **Voxtral** transformer for enhanced punctuation and grammar (optional)
- **Parakeet RNNT** via NVIDIA Riva endpoint (experimental)

All transcription happens locally on your machine—no cloud services, no data leaving your device.

## Key Features

- **🔒 Privacy-First**: 100% local processing, offline by default
- **⚡ Fast & Efficient**: Optimized for both CPU and GPU with quality presets
- **🎯 Accurate**: Leverages OpenAI's Whisper large-v3-turbo model
- **🎨 Flexible Interfaces**: CLI, GUI, and programmatic APIs
- **🔧 Configurable**: Multiple engines, quality presets, and customization options
- **📁 Multi-Format**: Supports MP3, WAV, AAC, and other common audio formats

## Quick Links

- **[Why Vociferous?](Why-Vociferous.md)** - Understand the problem we solve and who it's for
- **[How It Works](How-It-Works.md)** - Dive into the architecture and technical approach
- **[Getting Started](Getting-Started.md)** - Installation and first transcription
- **[Configuration](Configuration.md)** - Customize Vociferous to your needs
- **[Engines & Presets](Engines-and-Presets.md)** - Choose the right engine and quality settings
- **[Development](Development.md)** - Contribute to the project

## Use Cases

- **Developers**: Transcribe standup meetings and convert recordings to text for tickets and documentation
- **Students**: Transcribe lectures privately and offline for study materials
- **Content Creators**: Get accurate transcriptions without sending audio to third-party services
- **Researchers**: Process interview recordings locally while maintaining participant privacy

## Getting Started in 3 Steps

1. **Install**: `pip install -e .`
2. **Transcribe**: `vociferous transcribe meeting.wav`
3. **Enjoy**: Your transcript appears instantly!

See [Getting Started](Getting-Started.md) for detailed installation instructions.

## Community & Support

- **Repository**: [github.com/WanderingAstronomer/Vociferous](https://github.com/WanderingAstronomer/Vociferous)
- **Issues**: Report bugs or request features on GitHub Issues
- **Documentation**: Comprehensive docs in the `Planning and Documentation` directory

---

*This Wiki provides extensive documentation and reference. For quick usage instructions, see the [README](../README.md).*
