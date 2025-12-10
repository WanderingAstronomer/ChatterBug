# Vociferous Wiki Documentation

This directory contains the foundation for the Vociferous GitHub Wiki. These markdown files provide extensive documentation following a What/Why/How structure.

## Wiki Structure

### What - Overview
- **[Home.md](Home.md)**: Introduction to Vociferous, key features, and quick links

### Why - Problem & Solution
- **[Why-Vociferous.md](Why-Vociferous.md)**: Problem statement, use cases, and design philosophy

### How - Technical Details & Guides
- **[Getting-Started.md](Getting-Started.md)**: Installation, first transcription, and basic usage
- **[Configuration.md](Configuration.md)**: Configuration options, settings, and customization
- **[Engines-and-Presets.md](Engines-and-Presets.md)**: Engine comparison and quality presets
- **[How-It-Works.md](How-It-Works.md)**: Architecture, pipeline, and technical details
- **[Development.md](Development.md)**: Development setup, architecture, and contribution guidelines

### Navigation
- **[_Sidebar.md](_Sidebar.md)**: Wiki navigation sidebar

## Using These Files

### Option 1: GitHub Wiki
These files are ready to be published to the GitHub Wiki:

1. Navigate to your repository's Wiki tab on GitHub
2. Create pages with the same names (without .md extension)
3. Copy content from each markdown file
4. The _Sidebar.md provides navigation structure

### Option 2: Documentation Site
Use these files with documentation generators:
- **MkDocs**: Place in `docs/` directory with mkdocs.yml config
- **Docusaurus**: Adapt for Docusaurus structure
- **Jekyll**: Use with GitHub Pages

### Option 3: Keep In-Repo
These files can remain in the repository as reference documentation:
- Link to them from the main README
- Use as source of truth for documentation
- Sync to Wiki when needed

## Content Overview

### Comprehensive Coverage
The Wiki covers:
- ✅ **What**: Product overview and features
- ✅ **Why**: Problem statement and use cases  
- ✅ **How**: Architecture, usage, and development

### Target Audiences
- **Users**: Getting Started, Configuration, Engines & Presets
- **Developers**: Development, How It Works
- **Decision Makers**: Why Vociferous, What section

### Key Topics
- Installation and setup
- CLI and GUI usage
- Engine comparison (Whisper, Voxtral)
- Quality presets (fast, balanced, high-accuracy)
- Configuration system
- Architecture and design patterns
- Development setup and guidelines
- Contribution workflow

## Maintenance

### Updating Wiki
When code changes affect documentation:
1. Update relevant wiki files in this directory
2. Test examples and commands
3. Sync changes to GitHub Wiki if published

### Adding New Pages
To add new wiki pages:
1. Create markdown file in this directory
2. Follow existing structure and style
3. Add link to _Sidebar.md for navigation
4. Cross-link from related pages

## Style Guidelines

### Writing Style
- **Clear and concise**: No unnecessary jargon
- **Examples first**: Show, then explain
- **User-focused**: Address user needs directly
- **Consistent formatting**: Follow existing patterns

### Code Examples
- Include full commands with flags
- Show expected output when helpful
- Provide context for each example
- Test all examples for accuracy

### Structure
- Use hierarchical headings (H1 → H2 → H3)
- Include navigation links
- Add "Next Steps" sections
- Cross-reference related pages

## Quick Links

- **Main README**: [../README.md](../README.md)
- **Planning Docs**: [../Planning and Documentation](../Planning%20and%20Documentation/)
- **GUI Quickstart**: [../QUICKSTART_GUI.md](../QUICKSTART_GUI.md)

---

*This Wiki provides the comprehensive reference documentation. For quick usage, see the main [README](../README.md).*
