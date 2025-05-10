# -*- coding: utf-8 -*-
"""
@file: app.py
Generate PNG thumbnails (respecting freedesktop sizes).
Usage: app.py [-h] [-o OUTPUT] [-j JOBS] [-f|--force] input

This script generates PNG thumbnails of images in various sizes
(normal, large, x-large, xx-large) and saves them in a specified
output directory (should be `~/.cache/thumbnails/`).

- `Multiprocessing` to execute processing in parallel.
- `Pillow` library for image processing (resize).
- `Pillow.ImageDraw` to add a label to the thumbnail indicating the original file format.
- `Subprocess` to extract preview images from RAW files using `ExifTool`.
- `Subprocess` to handle rotation from Exif files using `ExifTool`.

The input can be either a file or a directory (which will be searched recursively).

Example of usage:
$ python3 app.py /mnt/sda1/photos/2025/ -o /home/thomas/.cache/thumbnails/ -j 16
$ python3 app.py /mnt/sda1/photos/2025/20250127/2J0A1537.cr3

Set thumnail-cache to handle more storage and keep it longer:
$ gsettings set org.gnome.nautilus.preferences thumbnail-limit 536870912000 (~500Gb)
$ gsettings set org.gnome.desktop.thumbnail-cache maximum-age 365
"""

import hashlib
import logging
import multiprocessing
import subprocess
import io

from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Optional, Union

from PIL import Image, ImageOps, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".cr2", ".cr3", ".arw"}
FONT = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf"
THUMBNAIL_CONFIG = {
    "normal": {
        "size": (128, 128),
        "font_size": 20,
    },
    "large": {
        "size": (256, 256),
        "font_size": 30,
    },
    "x-large": {
        "size": (512, 512),
        "font_size": 40,
    },
    # "xx-large": {
    #     "size": (1024, 1024),
    #     "font_size": 100,
    # },
}

from PIL import ImageDraw, ImageFont


def add_raw_label(image: Image.Image, label: str, text: str) -> Image.Image:
    """Add a label to the image indicating the original file format."""
    draw = ImageDraw.Draw(image)
    size = THUMBNAIL_CONFIG[label]["font_size"]
    x, y = 0, 0

    font = ImageFont.truetype(FONT, size)

    text_bbox = draw.textbbox((x, y), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    box_padding = int(size * 0.5)
    draw.rectangle(
        [
            x - box_padding,
            y - box_padding,
            x + text_width + box_padding,
            y + text_height + box_padding,
        ],
        fill="black",
    )
    draw.text((x, y), text, fill="white", font=font)
    return image


def extract_cr3_preview(image_path: Path, tag: str = "PreviewImage") -> io.BytesIO:
    """Extract preview image from RAW file using exiftool."""
    logging.info(f"Extracting preview from RAW: {image_path}")
    result = subprocess.run(
        ["exiftool", f"-{tag}", "-b", str(image_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(
            f"ExifTool failed on {image_path}:\n{result.stderr.decode().strip()}"
        )

    orient_proc = subprocess.run(
        ["exiftool", "-Orientation", "-s3", str(image_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    orientation_str = orient_proc.stdout.strip()

    rotate_map = {
        "Rotate 90 CW": -90,
        "Rotate 270 CW": -270,
        "Rotate 90 CCW": 90,
        "Rotate 180": 180,
    }
    img = Image.open(io.BytesIO(result.stdout))
    rotation = rotate_map.get(orientation_str, 0)
    if rotation:
        img = img.rotate(rotation, expand=True)

    img_bytes_io = io.BytesIO()
    img.save(img_bytes_io, format="JPEG")

    return img_bytes_io


def generate_thumbnails(
    image_path: Path, output_base: Path, overwrite=False
) -> Optional[str]:
    """Generate multiple size thumbnails for one image.
    If one size is missing, it will generate all sizes.
    overwrite (bool): If True, overwrite existing thumbnails."""

    uri = image_path.resolve().as_uri()
    hash_hex = hashlib.md5(uri.encode("utf-8")).hexdigest()
    out_filename = f"{hash_hex}.png"

    if not overwrite:
        all_exist = True
        for label in THUMBNAIL_CONFIG.keys():
            out_dir = output_base / label
            out_path = out_dir / out_filename
            if not out_path.exists():
                print(f"Thumbnail does not exist: {uri} {out_path}")
                all_exist = False
                break
        if all_exist:
            logging.info(f"All thumbnails already exist for: {image_path}")
            return None

    try:
        if image_path.suffix.lower() in {".cr3", ".cr2", ".arw"}:
            img = Image.open(extract_cr3_preview(image_path))
        else:
            img = Image.open(image_path)

        img = ImageOps.exif_transpose(img)

        metadata = PngInfo()
        metadata.add_text("Thumb::URI", uri)
        metadata.add_text("Thumb::MTime", str(int(image_path.stat().st_mtime)))
        metadata.add_text("Software", "make-thumbnail")

        for label, config in THUMBNAIL_CONFIG.items():
            size = config["size"]
            thumb = img.copy()
            thumb.thumbnail(size, Image.LANCZOS)

            out_dir = output_base / label
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / out_filename
            thumb.save(out_path, format="PNG", pnginfo=metadata)

            file_extension = image_path.suffix.lower()
            if file_extension in SUPPORTED_EXTENSIONS:
                thumb = add_raw_label(thumb, label, file_extension)
                thumb.save(out_path, format="PNG", pnginfo=metadata)

    except Exception as e:
        return f"{image_path}: {e}"
    return None


def collect_image_paths(input_path: Path) -> List[Path]:
    """Recursively collect image files from a path."""
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in SUPPORTED_EXTENSIONS else []
    elif input_path.is_dir():
        return [
            p for p in input_path.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
    else:
        raise ValueError("Input must be a file or directory.")


def process_images(
    image_paths: List[Path], output_dir: Path, num_workers: int, overwrite: bool = False
) -> List[str]:
    """Prepare threads to generate thumbnails in parallel."""
    errors = []
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(generate_thumbnails, path, output_dir, overwrite): path
            for path in image_paths
        }
        for future in tqdm(
            as_completed(futures),
            total=len(futures),
            desc="Generating thumbnails",
        ):
            error = future.result()
            if error:
                errors.append(error)
    return errors


def main(
    input_path: Union[str, Path],
    output_dir: Union[str, Path],
    num_workers: Optional[int] = None,
    overwrite: bool = False,
) -> None:
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    num_workers = num_workers or multiprocessing.cpu_count()

    try:
        image_paths = collect_image_paths(input_path)
    except ValueError as ve:
        logging.error(str(ve))
        return

    if not image_paths:
        logging.warning("No supported image files found.")
        return

    errors = process_images(image_paths, output_dir, num_workers, overwrite=overwrite)

    if errors:
        logging.warning("Some images failed to process:")
        for err in errors:
            logging.warning(err)
    else:
        logging.info("All thumbnails generated successfully.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate PNG thumbnails (freedesktop sizes)."
    )
    parser.add_argument("input", help="Input image file or directory.")
    parser.add_argument(
        "-o", "--output", default="thumbnails", help="Output directory."
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=None,
        help="Number of worker processes (default: all cores).",
    )
    parser.add_argument(
        "-f",
        action="store_true",
        help="Overwrite existing thumbnails.",
    )

    args = parser.parse_args()
    main(args.input, args.output, args.jobs, overwrite=args.f)
