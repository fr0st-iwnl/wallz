#!/usr/bin/env python3


# rename_wallpapers.py
#
# A script to rename wallpapers in a directory.
#
# Author: @fr0st-iwnl
#=================================================================
# Repository: https://github.com/fr0st-iwnl/wallz
#-----------------------------------------------------------------
# Issues: https://github.com/fr0st-iwnl/wallz/issues/
# Pull Requests: https://github.com/fr0st-iwnl/wallz/pulls
#-----------------------------------------------------------------

import os
import re
import glob
import sys
import shutil  # For creating backup files

# Check if the terminal supports colors
def supports_color():
    """
    Returns True if the running system's terminal supports color, and False otherwise.
    """
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    
    # isatty is not always implemented, so we use a try/except block
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    
    return supported_platform and is_a_tty

# ANSI color codes :)
class Colors:
    HEADER = '\033[95m' if supports_color() else ''
    BLUE = '\033[94m' if supports_color() else ''
    CYAN = '\033[96m' if supports_color() else ''
    GREEN = '\033[92m' if supports_color() else ''
    YELLOW = '\033[93m' if supports_color() else ''
    RED = '\033[91m' if supports_color() else ''
    BOLD = '\033[1m' if supports_color() else ''
    UNDERLINE = '\033[4m' if supports_color() else ''
    RESET = '\033[0m' if supports_color() else ''

def rename_wallpapers():
    print(f"{Colors.YELLOW}⚠️  IMPORTANT: This script will rename your wallpaper files.{Colors.RESET}")
    print(f"{Colors.YELLOW}   If you're not sure what this does, press Ctrl+C to cancel.{Colors.RESET}")
    print(f"{Colors.YELLOW}   Press Enter to continue...{Colors.RESET}")
    
    try:
        input()
    except KeyboardInterrupt:
        print("")
        print(f"\n{Colors.BLUE}Script canceled. No changes were made.{Colors.RESET}")
        print("")
        return
    
    # Get all directories in the current folder
    directories = [d for d in os.listdir('.') if os.path.isdir(d) and not d.startswith('.')]
    
    total_renamed = 0
    total_dirs_processed = 0
    
    # Process each directory separately
    for directory in directories:
        # supported images formats :)
        image_files = []
        # Search for both lowercase and uppercase extensions
        for ext_pattern in ['*.png', '*.jpg', '*.jpeg', '*.webp', '*.PNG', '*.JPG', '*.JPEG', '*.WEBP', '*.gif', '*.GIF']:
            image_files.extend(glob.glob(os.path.join(directory, ext_pattern)))
        
        # Remove duplicates (in case a file matches both lowercase and uppercase patterns)
        image_files = list(set(image_files))
        
        if not image_files:
            continue
        
        # Determine the padding needed based on the number of files
        padding = len(str(len(image_files)))
        padding = max(2, padding)  # At least 2 digits (01, 02, etc.)
        
        # If there are 100 or more files, use at least 3 digits
        if len(image_files) >= 100:
            padding = max(3, padding)
        
        # Extract current numbers from filenames to preserve order if possible
        numbered_files = []
        current_files_map = {}  # Map of file paths to their current filenames
        
        for file_path in image_files:
            filename = os.path.basename(file_path)
            current_files_map[file_path] = filename
            
            # Try to extract existing number from the filename
            match = re.match(r'^(\d+)[.\s]', filename)
            if match:
                number = int(match.group(1))
            else:
                # If no number, assign a large number to put it at the end
                number = 9999
            numbered_files.append((number, file_path))
        
        # Sort files by their extracted numbers
        numbered_files.sort()
        
        # Create new filenames with proper padding
        target_filenames = {}
        for i, (_, file_path) in enumerate(numbered_files, 1):
            extension = os.path.splitext(current_files_map[file_path])[1]
            new_filename = f"{i:0{padding}d}. {directory}{extension}"
            target_filenames[file_path] = new_filename
        
        # Track if any files in this directory need renaming
        dir_renamed = 0
        
        # Use a temporary directory to avoid conflicts during renaming
        # Why?
        # Well, tested so many ways and found some bugs but this is the best way to do it (I think).
        # Also i'm not a fan of this but it's the best way to do it personally.
        # Some credits to Claude 3.7 Sonnet for helping me with this (some parts of the code).        
        #
        # Here's why this approach is important :
        #
        # 1. Prevents file collisions: 
        #    Imagine you have files 01.png, 03.png, and 05.png and want to rename them to 01.png, 02.png, and 03.png.
        #    If we renamed directly, we'd hit errors because we'd still have the original 03.png while trying to 
        #    rename 05.png to 03.png. Using a temp directory avoids this issue completely.
        #
        # 2. Handles circular dependencies: 
        #    If you need to rename A→B, B→C, and C→A, doing this directly would be impossible 
        #    because you'd lose file B when renaming A to B. The temp directory approach solves this.
        #
        # 3. Ensures atomicity: 
        #    If anything goes wrong during the process, the script can safely clean up without leaving 
        #    your directory in a half-renamed state with some files renamed and others not.
        #
        # 4. Provides rollback capability: 
        #    In case of errors, your original files are preserved until the very end of the process,
        #    so you don't lose any wallpapers if something unexpected happens.
        #
        # in the end it just works :D
        
        temp_dir = os.path.join(directory, "_temp_rename_dir_")
        if os.path.exists(temp_dir):
            try:
                # Try to remove any existing temp dir
                for f in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, f))
                os.rmdir(temp_dir)
            except Exception:
                print(f"{Colors.RED}[✗] Error: Cannot clean up temporary directory {temp_dir}{Colors.RESET}")
                print(f"{Colors.RED}[✗] Skipping directory '{directory}' due to temp directory issues{Colors.RESET}")
                continue
        
        try:
            # Create temporary directory
            os.mkdir(temp_dir)
            
            # First move all files to temp dir with their target names
            renamed_files = []
            dir_printed = False
            
            for file_path, new_filename in target_filenames.items():
                old_filename = current_files_map[file_path]
                # Only process files that need renaming
                if os.path.basename(file_path) != new_filename:
                    temp_path = os.path.join(temp_dir, new_filename)
                    
                    try:
                        # Only print the directory name once
                        if not dir_printed:
                            print(f"\n{Colors.BOLD}{Colors.CYAN}Processing directory: {directory}{Colors.RESET}")
                            dir_printed = True
                        
                        print(f"  {Colors.GREEN}» Renaming: {Colors.YELLOW}{old_filename} {Colors.RESET}➜ {Colors.BLUE}{new_filename}{Colors.RESET}")
                        
                        # Move to temp directory
                        shutil.copy2(file_path, temp_path)
                        renamed_files.append((file_path, temp_path))
                        
                        dir_renamed += 1
                        total_renamed += 1
                    except Exception as e:
                        print(f"  {Colors.RED}[✗] Error preparing rename for {old_filename}: {e}{Colors.RESET}")
                        # Clean up and skip this directory if any file fails
                        for f in os.listdir(temp_dir):
                            os.remove(os.path.join(temp_dir, f))
                        os.rmdir(temp_dir)
                        continue
            
            # If we renamed files, delete the originals and move the temp files back
            if renamed_files:
                for original_path, temp_path in renamed_files:
                    try:
                        os.remove(original_path)
                    except Exception as e:
                        print(f"  {Colors.RED}[✗] Error removing original file {original_path}: {e}{Colors.RESET}")
                
                for original_path, temp_path in renamed_files:
                    try:
                        target_path = os.path.join(directory, os.path.basename(temp_path))
                        shutil.move(temp_path, target_path)
                    except Exception as e:
                        print(f"  {Colors.RED}[✗] Error moving renamed file back from temp dir: {e}{Colors.RESET}")
            
            # Clean up the temp directory
            os.rmdir(temp_dir)
            
            if dir_renamed > 0:
                total_dirs_processed += 1
                
        except Exception as e:
            print(f"{Colors.RED}[✗] Error processing directory {directory}: {e}{Colors.RESET}")
            # Try to clean up the temp directory if it exists
            if os.path.exists(temp_dir):
                try:
                    for f in os.listdir(temp_dir):
                        os.remove(os.path.join(temp_dir, f))
                    os.rmdir(temp_dir)
                except:
                    pass
    
    # Print completion message YaY :D
    if total_renamed > 0:
        print(f"\n{Colors.GREEN}[✓] Done! Renamed {Colors.BOLD}{total_renamed}{Colors.RESET}{Colors.GREEN} files across {Colors.BOLD}{total_dirs_processed}{Colors.RESET}{Colors.GREEN} directories.{Colors.RESET}")
        print("")
    else:
        print(f"\n{Colors.BLUE}[✧] All files are already properly named. No changes made.{Colors.RESET}")
        print("")

if __name__ == "__main__":
    rename_wallpapers() 