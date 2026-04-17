# Module Toolkit System Documentation

## Overview

The Module Toolkit is a comprehensive system for creating, managing, and customizing content for NeverEndingQuest. It provides tools for module building, monster asset generation, graphic pack management, and style customization.

## Table of Contents

1. [Architecture](#architecture)
2. [Core Components](#core-components)
3. [Data Structures](#data-structures)
4. [Graphic Packs](#graphic-packs)
5. [API Reference](#api-reference)
6. [Usage Examples](#usage-examples)
7. [Development Guide](#development-guide)

## Architecture

```
module_toolkit/
├── core/toolkit/              # Core toolkit services
│   ├── monster_generator.py   # AI image generation
│   ├── video_processor.py     # Video compression & processing
│   └── pack_manager.py        # Pack creation & management
├── data/                      # Data files
│   ├── bestiary/              # Monster compendium
│   │   └── monster_compendium.json
│   ├── styles/                # Style templates
│   │   └── style_templates.json
│   └── active_pack.json       # Active pack configuration
├── graphic_packs/             # Graphic pack storage
│   ├── default_photorealistic/
│   ├── anime_style/
│   └── [custom_packs]/
└── web/templates/             # Web interfaces
    └── module_toolkit.html    # Toolkit UI
```

## Core Components

### 1. Monster Generator (`monster_generator.py`)

Handles AI-powered image generation for monsters using various styles and models.

**Key Features:**
- Multiple AI model support (GPT-Image, DALL-E 3)
- Style template system (photorealistic, anime, etc.)
- Batch generation capabilities
- Account validation for model access
- Automatic thumbnail generation

**Main Class: `MonsterGenerator`**

```python
from core.toolkit.monster_generator import MonsterGenerator

generator = MonsterGenerator(api_key=YOUR_API_KEY)

# Generate single monster
result = generator.generate_monster_image(
    monster_id="aboleth",
    style="photorealistic",
    model="auto",
    pack_name="my_pack"
)

# Batch generate
results = await generator.batch_generate_pack(
    pack_name="my_pack",
    style="anime",
    monsters=["goblin", "orc", "troll"]
)
```

### 2. Video Processor (`video_processor.py`)

Processes monster animation videos with compression and thumbnail generation.

**Key Features:**
- Standardized compression (640x640 @ 1Mbps)
- Automatic thumbnail extraction
- Batch processing support
- URL import capability
- File deduplication via hashing

**Main Class: `VideoProcessor`**

```python
from core.toolkit.video_processor import VideoProcessor

processor = VideoProcessor()

# Process single video
result = processor.process_monster_video(
    input_path="raw_video.mp4",
    monster_id="dragon",
    pack_name="my_pack"
)

# Batch process
results = processor.batch_process_videos(
    video_files=[
        ("goblin.mp4", "goblin"),
        ("orc.mp4", "orc")
    ],
    pack_name="my_pack"
)
```

### 3. Pack Manager (`pack_manager.py`)

Manages graphic pack creation, import/export, and activation.

**Key Features:**
- Pack creation with templates
- ZIP import/export
- Pack activation system
- Version management
- Backup functionality

**Main Class: `PackManager`**

```python
from core.toolkit.pack_manager import PackManager

manager = PackManager()

# Create new pack
result = manager.create_pack(
    name="Fantasy Anime Pack",
    style_template="anime",
    author="YourName"
)

# Export pack
manager.export_pack("fantasy_anime_pack")

# Import pack
manager.import_pack("downloaded_pack.zip")

# Activate pack
manager.activate_pack("fantasy_anime_pack")
```

## Data Structures

### Monster Compendium (`monster_compendium.json`)

Central repository of all monster descriptions and metadata.

```json
{
  "version": "1.0.0",
  "monsters": {
    "aboleth": {
      "name": "Aboleth",
      "type": "aberration",
      "description": "Ancient fish-like horror...",
      "tags": ["aquatic", "psychic", "ancient"],
      "source_file": "generate_bestiary_batch1.py"
    }
  }
}
```

### Style Templates (`style_templates.json`)

Defines art styles and their generation parameters.

```json
{
  "styles": {
    "photorealistic": {
      "name": "Photorealistic",
      "base_prompt": "Create an ultra detailed photorealistic...",
      "modifiers": ["8K quality", "cinematic lighting"],
      "model_preference": "gpt-image-1",
      "model_settings": {
        "quality": "auto",
        "size": "1024x1024"
      }
    }
  }
}
```

### Pack Manifest (`manifest.json`)

Metadata for each graphic pack.

```json
{
  "name": "Fantasy Anime Pack",
  "version": "1.0.0",
  "author": "YourName",
  "style_template": "anime",
  "created_date": "2025-08-13",
  "monsters_included": ["goblin", "orc", "dragon"],
  "file_structure": {
    "images": "monsters/images/",
    "videos": "monsters/videos/",
    "thumbnails": "monsters/thumbnails/"
  }
}
```

## Graphic Packs

### Pack Structure

Each graphic pack follows this directory structure:

```
pack_name/
├── manifest.json              # Pack metadata
├── README.md                  # Pack documentation
└── monsters/
    ├── images/               # Monster portraits (PNG)
    │   ├── goblin.png
    │   └── orc.png
    ├── videos/               # Monster animations (MP4)
    │   ├── goblin_video.mp4
    │   └── orc_video.mp4
    └── thumbnails/           # UI thumbnails (JPG)
        ├── goblin_thumb.jpg
        └── orc_thumb.jpg
```

### Available Styles

1. **Photorealistic** - Ultra-realistic, detailed portraits
2. **Anime** - Japanese anime/manga style
3. **Studio Ghibli** - Whimsical, painterly style
4. **Dark Fantasy** - Gothic, atmospheric horror
5. **Comic Book** - Bold lines and vibrant colors
6. **Watercolor** - Traditional painting style
7. **Pixel Art** - Retro video game aesthetic
8. **Minimalist** - Clean, geometric designs

## API Reference

### Monster Generator API

#### `generate_monster_image(monster_id, style, model, pack_name)`
Generate a single monster image.

**Parameters:**
- `monster_id` (str): Monster identifier from bestiary
- `style` (str): Style template name
- `model` (str): AI model ("gpt-image-1", "dall-e-3", "auto")
- `pack_name` (str): Target pack name

**Returns:** Dictionary with generation results

#### `batch_generate_pack(pack_name, style, monsters, model)`
Generate images for multiple monsters.

**Parameters:**
- `pack_name` (str): Target pack name
- `style` (str): Style template
- `monsters` (list): Monster IDs or None for all
- `model` (str): AI model preference

**Returns:** Dictionary with batch results

### Video Processor API

#### `process_monster_video(input_path, monster_id, pack_name)`
Process and compress a monster video.

**Parameters:**
- `input_path` (str): Path to input video
- `monster_id` (str): Monster identifier
- `pack_name` (str): Target pack name

**Returns:** Dictionary with processing results

### Pack Manager API

#### `create_pack(name, style_template, author, description)`
Create a new graphic pack.

**Parameters:**
- `name` (str): Pack name
- `style_template` (str): Base style
- `author` (str): Pack creator
- `description` (str): Pack description

**Returns:** Dictionary with creation results

#### `import_pack(zip_path)`
Import a pack from ZIP file.

**Parameters:**
- `zip_path` (str): Path to ZIP file

**Returns:** Dictionary with import results

#### `export_pack(pack_name, output_dir)`
Export a pack to ZIP file.

**Parameters:**
- `pack_name` (str): Pack to export
- `output_dir` (str): Output directory

**Returns:** Dictionary with export results

## Usage Examples

### Creating a Custom Anime Pack

```python
# 1. Create the pack
manager = PackManager()
manager.create_pack(
    name="Anime Adventure Pack",
    style_template="anime",
    author="YourName",
    description="High-quality anime-style monsters"
)

# 2. Generate monster images
generator = MonsterGenerator(api_key=API_KEY)
monsters = ["goblin", "orc", "dragon", "skeleton"]

for monster in monsters:
    generator.generate_monster_image(
        monster_id=monster,
        style="anime",
        model="dall-e-3",
        pack_name="anime_adventure_pack"
    )

# 3. Process videos (if available)
processor = VideoProcessor()
processor.process_monster_video(
    input_path="goblin_animation.mp4",
    monster_id="goblin",
    pack_name="anime_adventure_pack"
)

# 4. Export the pack
manager.export_pack("anime_adventure_pack")
```

### Batch Processing Workflow

```python
import asyncio
from core.toolkit import MonsterGenerator, VideoProcessor, PackManager

async def create_complete_pack(pack_name, style):
    # Initialize services
    generator = MonsterGenerator(api_key=API_KEY)
    processor = VideoProcessor()
    manager = PackManager()
    
    # Create pack
    manager.create_pack(pack_name, style)
    
    # Generate all images
    await generator.batch_generate_pack(
        pack_name=pack_name,
        style=style,
        model="auto"
    )
    
    # Process any available videos
    video_files = [
        ("videos/goblin.mp4", "goblin"),
        ("videos/orc.mp4", "orc")
    ]
    
    processor.batch_process_videos(
        video_files=video_files,
        pack_name=pack_name
    )
    
    # Export pack
    manager.export_pack(pack_name)
    
    print(f"Pack '{pack_name}' created successfully!")

# Run
asyncio.run(create_complete_pack("my_custom_pack", "dark_fantasy"))
```

## Development Guide

### Adding New Styles

1. Edit `data/styles/style_templates.json`
2. Add new style entry with:
   - Base prompt
   - Style modifiers
   - Model preference
   - Model settings

```json
"new_style": {
  "name": "New Style Name",
  "description": "Style description",
  "base_prompt": "Create a [style] monster portrait",
  "modifiers": ["modifier1", "modifier2"],
  "model_preference": "dall-e-3",
  "model_settings": {
    "quality": "standard",
    "size": "1024x1024",
    "style": "vivid"
  }
}
```

### Adding New Monsters

1. Edit `data/bestiary/monster_compendium.json`
2. Add monster entry with:
   - Display name
   - Type (aberration, beast, etc.)
   - Detailed description
   - Tags for categorization

```json
"new_monster": {
  "name": "New Monster",
  "type": "monstrosity",
  "description": "Detailed visual description...",
  "tags": ["large", "magical", "flying"]
}
```

### Custom Processing Settings

Override default video compression settings:

```python
custom_settings = {
    "codec": "libx264",
    "preset": "medium",
    "bitrate": "1500k",
    "resolution": "1024x1024",
    "fps": 30
}

processor.process_monster_video(
    input_path="high_quality.mp4",
    monster_id="boss_monster",
    pack_name="hd_pack",
    custom_settings=custom_settings
)
```

### CLI Tools

The toolkit includes command-line interfaces for each component:

```bash
# Monster generation
python -m core.toolkit.monster_generator goblin --style anime --pack my_pack

# Video processing
python -m core.toolkit.video_processor input.mp4 goblin --pack my_pack

# Pack management
python -m core.toolkit.pack_manager create "My Pack" --style photorealistic
python -m core.toolkit.pack_manager list
python -m core.toolkit.pack_manager export my_pack
python -m core.toolkit.pack_manager import downloaded_pack.zip
python -m core.toolkit.pack_manager activate my_pack
```

## Integration with Main Game

### Activating Packs in Game

The main game reads from `data/active_pack.json` to determine which pack to use:

```python
# In game code
from core.toolkit.pack_manager import PackManager

manager = PackManager()
active_pack = manager.get_active_pack()

# Load monster assets
monster_image = f"graphic_packs/{active_pack}/monsters/images/{monster_id}.png"
monster_video = f"graphic_packs/{active_pack}/monsters/videos/{monster_id}_video.mp4"
```

### Settings Interface

The game settings will include a dropdown to select active packs:

```javascript
// In game_interface.html
fetch('/api/toolkit/packs')
  .then(response => response.json())
  .then(packs => {
    // Populate pack selector
    packs.forEach(pack => {
      const option = new Option(pack.display_name, pack.name);
      packSelector.add(option);
    });
  });
```

## Troubleshooting

### Common Issues

1. **GPT-Image access denied**
   - Solution: Account validation required, falls back to DALL-E 3

2. **ffmpeg not found**
   - Solution: Install ffmpeg system-wide

3. **Pack import fails**
   - Check manifest.json exists in ZIP
   - Verify ZIP structure matches expected format

4. **Generation rate limits**
   - Batch generation includes 2-second delays
   - Consider using async processing

## Future Enhancements

- [ ] Web-based toolkit interface
- [ ] Real-time generation progress tracking
- [ ] Community pack marketplace
- [ ] Custom model training support
- [ ] Animation generation from static images
- [ ] Style mixing and blending
- [ ] Automated quality assessment
- [ ] Pack version control and updates

## License

The Module Toolkit is part of NeverEndingQuest and follows the same licensing terms. Generated content may have additional licensing based on the AI models used.

## Support

For issues or questions about the Module Toolkit, please refer to the main project documentation or create an issue on GitHub.