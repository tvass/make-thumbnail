# make-thumbnail

This is my own implementation of a FreeDesktop-compliant thumbnail generator for images, including RAW formats.

## Features

- Generates PNG thumbnails in standard FreeDesktop sizes (`normal`, `large`, `x-large`, `xx-large`)
- Uses `Pillow` for image resizing and drawing labels with original file formats
- Leverages `ExifTool` (via `subprocess`) to:
  - Extract previews from RAW files
  - Correct image orientation using EXIF metadata
- Supports multiprocessing for fast, parallel thumbnail generation
- Works with both individual files and directories (recursive)

## Usage

```bash
python3 app.py [-h] [-o OUTPUT] [-j JOBS] [-f|--force] input
```

Examples

```
python3 app.py /mnt/sda1/photos/2025/ -o ~/.cache/thumbnails/ -j 16
python3 app.py /mnt/sda1/photos/2025/20250127/2J0A1537.cr3
```

## Tips
To increase Nautilus' thumbnail cache size and retention:

```
gsettings set org.gnome.nautilus.preferences thumbnail-limit 536870912000  # (~500 GB)
gsettings set org.gnome.desktop.thumbnail-cache maximum-age 365            # (365 days)
```

![Example Thumbnail](example.png)