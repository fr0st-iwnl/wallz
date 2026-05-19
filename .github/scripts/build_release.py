#!/usr/bin/env python3

# imports
import argparse
import os
import shutil
import zipfile
from pathlib import Path


# variables
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
SCRIPT_NAME = 'rename_wallpapers.py'
ZIP_NAME = 'wallz.zip'
NOTES_NAME = 'release-notes.md'


def parse_args():
    parser = argparse.ArgumentParser(description='Build Wallz release assets.')
    parser.add_argument('--tag', required=True, help='release tag name')
    parser.add_argument('--repo', required=True, help='GitHub repository, ex: fr0st-xyz/wallz')
    parser.add_argument('--output', required=True, help='output directory for release files')
    return parser.parse_args()


def format_size(size_bytes):
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(size_bytes)
    unit = units[0]

    for candidate in units:
        unit = candidate
        if size < 1024 or candidate == units[-1]:
            break
        size /= 1024

    if unit == 'B':
        return f'{int(size)} {unit}'
    if size >= 100:
        return f'{size:.0f} {unit}'
    if size >= 10:
        return f'{size:.1f} {unit}'
    return f'{size:.2f} {unit}'


def display_tag(tag):
    return tag if tag.lower().startswith('v') else f'v{tag}'


def is_wallpaper_directory(path):
    if not path.is_dir():
        return False
    if path.name.startswith('.'):
        return False
    return any(file.suffix.lower() in IMAGE_EXTENSIONS for file in path.rglob('*') if file.is_file())


def collect_wallpaper_directories(repo_root):
    return sorted(
        [path for path in repo_root.iterdir() if is_wallpaper_directory(path)],
        key=lambda path: path.name.lower(),
    )


def build_zip(repo_root, output_dir, wallpaper_dirs):
    zip_path = output_dir / ZIP_NAME
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for directory in wallpaper_dirs:
            for file_path in sorted(directory.rglob('*')):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(repo_root))
    return zip_path


def copy_script(repo_root, output_dir):
    source = repo_root / SCRIPT_NAME
    target = output_dir / SCRIPT_NAME
    shutil.copy2(source, target)
    return target


def build_release_notes(output_dir, tag, repo, zip_path, script_path):
    release_url = f'https://github.com/{repo}/releases/download/{tag}'
    zip_size = format_size(zip_path.stat().st_size)
    script_size = format_size(script_path.stat().st_size)
    notes = f"""# 🎨 Wallz Pack {display_tag(tag)}

### 📥 Downloads

<table>
  <tbody>
    <tr>
      <td>📦 ZIP Archive</td>
      <td>🏷️ Size: {zip_size}</td>
      <td><a href="{release_url}/{ZIP_NAME}">{ZIP_NAME}</a></td>
    </tr>
    <tr>
      <td>🐍 Python Script</td>
      <td>📄 File: {script_size}</td>
      <td><a href="{release_url}/{SCRIPT_NAME}">{SCRIPT_NAME}</a></td>
    </tr>
  </tbody>
</table>

### 📒 Notes

- `wallz.zip` only includes wallpaper folders.
- Repo files like `.git`, `.github`, `README.md`, `LICENSE`, and `CONTRIBUTING.md` are not included in the ZIP.
- Download the Python script separately if you want the rename tool.
"""
    notes_path = output_dir / NOTES_NAME
    notes_path.write_text(notes, encoding='utf-8')
    return notes_path


def main():
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    wallpaper_dirs = collect_wallpaper_directories(repo_root)
    if not wallpaper_dirs:
        raise SystemExit('No wallpaper directories found.')

    zip_path = build_zip(repo_root, output_dir, wallpaper_dirs)
    script_path = copy_script(repo_root, output_dir)
    build_release_notes(output_dir, args.tag, args.repo, zip_path, script_path)


if __name__ == '__main__':
    main()
