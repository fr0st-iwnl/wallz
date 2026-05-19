#!/usr/bin/env python3

# rename_wallpapers.py
#
# A script to rename wallpapers in a directory.
#
# Author: @fr0st.xyz
#=================================================================
# Repository: https://github.com/fr0st-xyz/wallz
#-----------------------------------------------------------------
# Issues: https://github.com/fr0st-xyz/wallz/issues/
# Pull Requests: https://github.com/fr0st-xyz/wallz/pulls
#-----------------------------------------------------------------

# -----------------------------
# Imports
# -----------------------------
import os
import re
import glob
import sys
import argparse
import shutil  # For creating backup files
import json
import unicodedata

# disables __pycache__ folder
sys.dont_write_bytecode = True

try:
    from wcwidth import wcwidth as _wcwidth
except Exception:
    _wcwidth = None
from datetime import datetime


# -----------------------------
# Shared state and text
# -----------------------------
LAST_ROOT_PICK_CONTEXT = None
LAST_VIEW_CONTEXT = None
PICKER_BACK_TO_QUESTION = '__WALLZ_PICKER_BACK_TO_QUESTION__'

# File types
SUPPORTED_IMAGE_PATTERNS = ['*.png', '*.jpg', '*.jpeg', '*.webp', '*.PNG', '*.JPG', '*.JPEG', '*.WEBP', '*.gif', '*.GIF']

# Picker text
HELP_LINES = (
    '[↑/↓] Move   [Enter] Open   [Space] Choose',
    '[/] Search   [Backspace] Back   [Tab] Forward',
    '[Esc] Back   [Ctrl+C] Cancel',
)

# Texts
NO_FOLDERS_FOUND_TEXT = 'No folders found.'
DIVIDER_55 = '─' * 55
CANCELLED_MESSAGE = '👋 Cancelled - your files are unchanged.'
ALREADY_NAMED_MESSAGE = '[✧] All files are already properly named. No changes made.'
NO_CHANGES_HERE_MESSAGE = '[✧] No folders found here. No changes made.'
CHOOSE_ANOTHER_FOLDER_MESSAGE = 'Choose another folder.'
BACKUP_DIR_NAME = '.wallz-backups'

# Check if terminal supports colors
def supports_color():
    """Return True when ANSI colors should work in this terminal."""
    if os.environ.get('WT_SESSION'):
        return True
    
    if sys.platform == 'win32':
        import platform
        try:
            version = platform.version().split('.')
            major_version = int(version[0])
            if major_version >= 10:
                return True
        except:
            pass
        
        if 'ANSICON' in os.environ:
            return True
        
        if any(term in os.environ.get('TERM', '') for term in ['xterm', 'color']):
            return True
    
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    
    return supported_platform and is_a_tty

# Colors
class Colors:
    BLUE = '\033[94m' if supports_color() else ''
    CYAN = '\033[96m' if supports_color() else ''
    GREEN = '\033[92m' if supports_color() else ''
    YELLOW = '\033[93m' if supports_color() else ''
    RED = '\033[91m' if supports_color() else ''
    BOLD = '\033[1m' if supports_color() else ''
    RESET = '\033[0m' if supports_color() else ''


# -----------------------------
# Terminal helpers
# -----------------------------
def terminal_size(default_columns=80, default_rows=24):
    try:
        size = shutil.get_terminal_size((default_columns, default_rows))
        return size.columns, size.lines
    except Exception:
        return default_columns, default_rows


def strip_ansi(text):
    return re.sub(r'\033\[[0-9;?]*[A-Za-z]', '', str(text))


def char_width(char):
    # Keep box width stable with emojis and wide Unicode characters.
    if _wcwidth is not None:
        width = _wcwidth(char)
        return max(0, width)

    if unicodedata.combining(char):
        return 0
    if ord(char) in range(0xFE00, 0xFE0F + 1):
        return 0
    if unicodedata.east_asian_width(char) in ('W', 'F'):
        return 2
    if (
        0x1F000 <= ord(char) <= 0x1FAFF or
        0x2600 <= ord(char) <= 0x27BF
    ):
        return 2
    return 1

def visible_width(text):
    return sum(char_width(ch) for ch in strip_ansi(text))


def fit_text(text, width):
    text = str(text)
    if width <= 0:
        return ''
    if visible_width(text) <= width:
        return text

    ellipsis = '...'
    target = max(0, width - visible_width(ellipsis))
    output = ''
    used = 0

    for char in text:
        char_w = char_width(char)
        if used + char_w > target:
            break
        output += char
        used += char_w

    return output + ellipsis


def pad_text(text, width):
    text = fit_text(text, width)
    padding = ' ' * max(0, width - visible_width(text))
    return text + padding


def clear_terminal_area():
    sys.stdout.write('\033[?25l')  # hide cursor
    sys.stdout.write('\033[H\033[J')
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write('\033[?25h')
    sys.stdout.flush()


def get_scroll_window(total_items, selected, max_visible=5):
    if total_items <= max_visible:
        return 0, total_items

    half = max_visible // 2
    start = selected - half
    start = max(0, start)
    start = min(start, total_items - max_visible)
    return start, start + max_visible


def get_visible_entries(entries, selected, max_visible=5):
    start, end = get_scroll_window(len(entries), selected, max_visible=max_visible)
    return entries[start:end], start


# -----------------------------
# Picker drawing
# -----------------------------
def box_width(width):
    return max(44, min(width - 4, 68))


def print_card_top(inner_width):
    print(f"{Colors.CYAN}┌{'─' * inner_width}┐{Colors.RESET}")


def print_card_bottom(inner_width):
    print(f"{Colors.CYAN}└{'─' * inner_width}┘{Colors.RESET}")


def print_card_line(text='', inner_width=70, color=''):
    # Use an absolute cursor column so the right border stays aligned.
    content_width = inner_width - 2
    clean = fit_text(text, content_width)
    border_column = inner_width + 2

    sys.stdout.write(f"{Colors.CYAN}│{Colors.RESET} {color}{clean}{Colors.RESET}")
    sys.stdout.write(f"\033[{border_column}G{Colors.CYAN}│{Colors.RESET}\n")


def draw_picker_box(path, entries, selected, width, search_query='', search_active=False):
    inner_width = box_width(width)
    content_width = inner_width - 2
    visible_entries, start = get_visible_entries(entries, selected, max_visible=5)

    print_card_top(inner_width)
    print_card_line(f"📂 {path}", inner_width, Colors.BOLD + Colors.BLUE)
    print_card_line('─' * content_width, inner_width, Colors.CYAN)
    search_text = get_search_text(search_query)
    print_card_line(search_text, inner_width, Colors.YELLOW if (search_active or search_query) else Colors.CYAN)

    if not entries:
        print_card_line(NO_FOLDERS_FOUND_TEXT, inner_width, Colors.YELLOW)
    else:
        for offset, item in enumerate(visible_entries):
            index = start + offset
            display = item['display']
            is_selected = index == selected
            pointer = '➜' if is_selected else ' '

            row = f"{pointer} {display}"

            if is_selected:
                print_card_line(row, inner_width, Colors.BOLD + Colors.YELLOW)
            elif item.get('parent'):
                print_card_line(row, inner_width, Colors.YELLOW)
            else:
                print_card_line(row, inner_width, Colors.BLUE)

    print_card_line('', inner_width)
    print_card_line(f"{selected + 1} / {len(entries)}" if entries else '0 / 0', inner_width, Colors.CYAN)
    print_card_line('─' * content_width, inner_width, Colors.CYAN)
    for help_line in HELP_LINES:
        print_card_line(help_line, inner_width, Colors.YELLOW)
    print_card_bottom(inner_width)


def get_search_text(search_query):
    return f"  🔎 /{search_query}"


def plain_box_line(text='', inner_width=70):
    return '│ ' + pad_text(text, inner_width - 2) + ' │'


# -----------------------------
# Prompts
# -----------------------------
def ask_yes_no(question, default_no=True):
    suffix = '[y/N]' if default_no else '[Y/n]'
    while True:
        if question:
            prompt = f"{Colors.BOLD}{question}{Colors.RESET} {Colors.YELLOW}{suffix}{Colors.RESET}: "
        else:
            prompt = f"{Colors.YELLOW}{suffix}{Colors.RESET}: "
        answer = input(prompt).strip().lower()
        if not answer:
            return not default_no
        if answer in ['y', 'yes']:
            return True
        if answer in ['n', 'no']:
            return False
        print(f"{Colors.YELLOW}Please type y or n.{Colors.RESET}")


def ask_folder_question(number, path):
    print(f"{Colors.CYAN}{DIVIDER_55}{Colors.RESET}")
    print()
    print(f"{Colors.BOLD}{Colors.YELLOW}{number}. Is this the folder you want to organize?{Colors.RESET}")
    print()
    print(f"{Colors.BLUE}📂 {path}{Colors.RESET}")
    print()
    return ask_yes_no('', default_no=False)


def confirm_continue():
    print()
    print(f"{Colors.CYAN}{DIVIDER_55}{Colors.RESET}")
    print(f"{Colors.RED}⚠️ This will rename files in the selected folder.{Colors.RESET}")
    print()
    answer = input(f"{Colors.BOLD}Type YES to continue: {Colors.RESET}").strip()
    return answer == 'YES'


# -----------------------------
# Picker data
# -----------------------------
def list_folder_entries(path, query=''):
    try:
        dirs = [
            name for name in sorted(os.listdir(path), key=str.lower)
            if os.path.isdir(os.path.join(path, name)) and not name.startswith('.')
        ]
    except PermissionError:
        raise

    if query:
        lowered = query.lower()
        dirs = [name for name in dirs if lowered in name.lower()]

    entries = [{'name': '..', 'display': '↩️ ../', 'parent': True}]
    entries.extend({'name': name, 'display': f'📁 {name}/', 'parent': False} for name in dirs)
    return entries


def restore_selected_entry(entries, saved_name, saved_index):
    if saved_name:
        for idx, item in enumerate(entries):
            if item['name'] == saved_name:
                return idx

    if entries:
        return min(saved_index, len(entries) - 1)

    return 0


# -----------------------------
# Picker input
# -----------------------------

# Windows key reader
def get_windows_key():
    import msvcrt

    key = msvcrt.getch()
    if key in (b'\x00', b'\xe0'):
        key2 = msvcrt.getch()
        if key2 == b'H':
            return 'UP'
        if key2 == b'P':
            return 'DOWN'
        if key2 == b'K':
            return 'LEFT'
        if key2 == b'M':
            return 'RIGHT'
        return 'OTHER'

    if key in (b'\x03',):
        return 'CANCEL'
    if key in (b'\x1b',):
        return 'ESC'
    if key in (b'\r', b'\n'):
        return 'ENTER'
    if key == b' ':
        return 'SPACE'
    if key == b'\t':
        return 'TAB'
    if key == b'/':
        return '/'
    if key in (b'\x08', b'\x7f'):
        return 'BACKSPACE'

    try:
        return key.decode('utf-8')
    except Exception:
        return 'OTHER'

# Linux/macOS key reader
def get_posix_key():
    import os
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        key = os.read(fd, 1)

        if key == b'\x1b':
            ready, _, _ = select.select([fd], [], [], 0.03)
            if not ready:
                return 'ESC'

            next1 = os.read(fd, 1)
            if next1 == b'[':
                ready, _, _ = select.select([fd], [], [], 0.03)
                if not ready:
                    return 'OTHER'
                next2 = os.read(fd, 1)
                if next2 == b'A':
                    return 'UP'
                if next2 == b'B':
                    return 'DOWN'
                if next2 == b'C':
                    return 'RIGHT'
                if next2 == b'D':
                    return 'LEFT'
                return 'OTHER'
            return 'ESC'
        if key == b'\x03':
            return 'CANCEL'
        if key in (b'\r', b'\n'):
            return 'ENTER'
        if key == b' ':
            return 'SPACE'
        if key == b'\t':
            return 'TAB'
        if key == b'/':
            return '/'
        if key in (b'\x08', b'\x7f'):
            return 'BACKSPACE'
        try:
            text = key.decode('utf-8')
        except Exception:
            return 'OTHER'
        if text.isprintable():
            return text
        return 'OTHER'
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# -----------------------------
# Picker flow
# -----------------------------
def run_picker(start_path, initial_selected_name, render, read_key):
    global LAST_ROOT_PICK_CONTEXT
    global LAST_VIEW_CONTEXT

    current_path = os.path.abspath(start_path)
    selected = 0
    pending_initial_selected_name = initial_selected_name
    search_query = ''
    search_active = False
    search_saved_name = None
    search_saved_selected = 0
    last_child_by_parent = {}

    while True:
        try:
            entries = list_folder_entries(current_path, search_query)
        except PermissionError:
            current_path = os.path.dirname(current_path)
            selected = 0
            search_query = ''
            search_active = False
            continue

        if pending_initial_selected_name:
            for idx, item in enumerate(entries):
                if item['name'] == pending_initial_selected_name:
                    selected = idx
                    break
            pending_initial_selected_name = None

        if search_query and search_saved_name:
            for idx, item in enumerate(entries):
                if item['name'] == search_saved_name:
                    selected = idx
                    break

        selected = min(selected, max(0, len(entries) - 1))
        render(
            current_path,
            entries,
            selected,
            search_query=search_query,
            search_active=search_active,
        )
        key = read_key()

        if search_active and key == 'BACKSPACE':
            search_query = search_query[:-1]
            if search_query:
                selected = 0
            else:
                selected = min(search_saved_selected, max(0, len(entries) - 1))
        elif search_active and isinstance(key, str) and len(key) == 1 and key.isprintable() and key not in ['\r', '\n', '/']:
            search_query += key
            selected = 0
        elif key == 'UP' and entries:
            selected = (selected - 1) % len(entries)
        elif key == 'DOWN' and entries:
            selected = (selected + 1) % len(entries)
        elif key in ('BACKSPACE', 'LEFT'):
            parent = os.path.dirname(current_path)
            if parent != current_path:
                last_child_by_parent[parent] = current_path
                current_path = parent
                selected = 0
                search_query = ''
        elif key == 'TAB':
            next_path = last_child_by_parent.get(current_path)
            if next_path and os.path.isdir(next_path):
                current_path = next_path
                selected = 0
                search_query = ''
        elif key == '/':
            if not search_active:
                search_active = True
                search_query = ''
                search_saved_selected = selected
                search_saved_name = entries[selected]['name'] if entries else None
        elif key == 'ESC' and search_active:
            search_active = False
            search_query = ''
            full_entries = list_folder_entries(current_path, '')
            selected = restore_selected_entry(full_entries, search_saved_name, search_saved_selected)
            search_saved_name = None
        elif key == 'ESC':
            if entries:
                LAST_VIEW_CONTEXT = (current_path, entries[selected]['name'])
            return PICKER_BACK_TO_QUESTION
        elif key == 'CANCEL':
            return None
        elif key == 'SPACE' and entries:
            choice = entries[selected]['name']
            LAST_ROOT_PICK_CONTEXT = (current_path, choice)
            if choice == '..':
                parent = os.path.dirname(current_path)
                return parent if parent != current_path else current_path
            return os.path.join(current_path, choice)
        elif key == 'ENTER' and entries:
            choice = entries[selected]['name']
            if choice == '..':
                parent = os.path.dirname(current_path)
                if parent != current_path:
                    last_child_by_parent[parent] = current_path
                    current_path = parent
            else:
                new_path = os.path.join(current_path, choice)
                last_child_by_parent[current_path] = new_path
                current_path = new_path
            selected = 0
            search_query = ''

def render_windows_picker(path, entries, selected, search_query='', search_active=False):
    width, _ = terminal_size()
    clear_terminal_area()
    draw_picker_box(
        path,
        entries,
        selected,
        width,
        search_query=search_query,
        search_active=search_active,
    )

def pick_root_directory_windows(start_path, initial_selected_name=None):
    try:
        return run_picker(
            start_path,
            initial_selected_name,
            render_windows_picker,
            get_windows_key,
        )
    finally:
        show_cursor()

# Windows uses msvcrt
# Linux/macOS use ANSI drawing + raw terminal input
def pick_root_directory(start_path, initial_selected_name=None):
    if sys.platform == 'win32':
        return pick_root_directory_windows(start_path, initial_selected_name)

    try:
        import termios  # noqa: F401
        import tty  # noqa: F401
    except Exception:
        print(f"{Colors.YELLOW}⚠️ Arrow key picker is not available in this terminal.{Colors.RESET}")
        print(f"{Colors.YELLOW}   Using a simple number picker instead.{Colors.RESET}")
        print()
        return pick_root_directory_fallback(start_path)

    try:
        return run_picker(
            start_path,
            initial_selected_name,
            render_windows_picker,
            get_posix_key,
        )
    finally:
        show_cursor()


def pick_root_directory_fallback(start_path):
    current_path = os.path.abspath(start_path)

    while True:
        print()
        print(f"{Colors.BOLD}Current folder:{Colors.RESET} {current_path}")
        dirs = [
            name for name in sorted(os.listdir(current_path), key=str.lower)
            if os.path.isdir(os.path.join(current_path, name)) and not name.startswith('.')
        ]

        print("  0. Select this folder")
        print("  1. ../")
        for idx, name in enumerate(dirs, start=2):
            print(f"  {idx}. {name}/")

        choice = input("Choose a number or type q to cancel: ").strip().lower()
        if choice == 'q':
            return None
        if not choice.isdigit():
            continue

        choice = int(choice)
        if choice == 0:
            return current_path
        if choice == 1:
            parent = os.path.dirname(current_path)
            if parent != current_path:
                current_path = parent
        elif 2 <= choice < len(dirs) + 2:
            current_path = os.path.join(current_path, dirs[choice - 2])


def get_last_root_pick_context(picked_path):
    global LAST_ROOT_PICK_CONTEXT

    if LAST_ROOT_PICK_CONTEXT:
        picker_path, selected_name = LAST_ROOT_PICK_CONTEXT
        LAST_ROOT_PICK_CONTEXT = None
        return picker_path, selected_name

    return os.path.dirname(picked_path), os.path.basename(picked_path)


# -----------------------------
# Rename planning
# -----------------------------
def get_image_files(directory):
    image_files = []
    for ext_pattern in SUPPORTED_IMAGE_PATTERNS:
        image_files.extend(glob.glob(os.path.join(directory, ext_pattern)))
    
    image_files = list(set(image_files))
    return image_files


def build_plan_for_directory(directory):
    image_files = get_image_files(directory)
    
    if not image_files:
        return []
    
    padding = len(str(len(image_files)))
    padding = max(2, padding)
    
    if len(image_files) >= 100:
        padding = max(3, padding)
    
    numbered_files = []
    unnumbered_files = []
    current_files_map = {}
    max_existing_digits = 0
    
    for file_path in image_files:
        filename = os.path.basename(file_path)
        current_files_map[file_path] = filename
        
        match = re.match(r'^(\d+)[.\s]', filename)
        if match:
            number_str = match.group(1)
            number = int(number_str)
            max_existing_digits = max(max_existing_digits, len(number_str))
            numbered_files.append((number, file_path))
        else:
            unnumbered_files.append(file_path)
    
    numbered_files.sort(key=lambda x: (x[0], current_files_map[x[1]].lower()))
    unnumbered_files.sort(key=lambda p: current_files_map[p].lower())
    
    padding = max(padding, max_existing_digits)
    
    target_numbers = {}
    expected = 1
    renumber_from = None
    
    for idx, (number, file_path) in enumerate(numbered_files):
        if number == expected:
            target_numbers[file_path] = number
            expected += 1
            continue
        renumber_from = idx
        break
    
    if renumber_from is None:
        renumber_from = len(numbered_files)
    
    next_number = expected
    for number, file_path in numbered_files[renumber_from:]:
        target_numbers[file_path] = next_number
        next_number += 1
    
    for file_path in unnumbered_files:
        target_numbers[file_path] = next_number
        next_number += 1
    
    target_filenames = {}
    for file_path, number in target_numbers.items():
        extension = os.path.splitext(current_files_map[file_path])[1]
        new_filename = f"{number:0{padding}d}. {os.path.basename(directory)}{extension}"
        target_filenames[file_path] = new_filename
    
    changes = []
    for file_path, new_filename in target_filenames.items():
        old_filename = current_files_map[file_path]
        if os.path.basename(file_path) != new_filename:
            changes.append({
                'directory': directory,
                'old_path': file_path,
                'new_path': os.path.join(directory, new_filename),
                'old_filename': old_filename,
                'new_filename': new_filename,
            })

    changes.sort(key=lambda item: item['old_filename'].lower())
    return changes


def build_full_plan(selected_directories):
    plan = []
    for directory in selected_directories:
        plan.extend(build_plan_for_directory(directory))
    return plan


def count_images_in_directories(directories):
    total = 0
    for directory in directories:
        total += len(get_image_files(directory))
    return total


def get_target_directories(root_path):
    directories = [
        os.path.join(root_path, name)
        for name in os.listdir(root_path)
        if os.path.isdir(os.path.join(root_path, name)) and not name.startswith('.')
    ]
    directories.sort(key=lambda path: os.path.basename(path).lower())
    return directories


# -----------------------------
# Apply and rollback
# -----------------------------
def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='A script to rename wallpapers in a directory.')
    parser.add_argument(
        '--root',
        metavar='PATH',
        help='rename wallpaper folders under this path',
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='skip prompts and use the selected path directly',
    )
    parser.add_argument(
        '--save-backup',
        action='store_true',
        help=f'save a rollback file in {BACKUP_DIR_NAME}/ before renaming',
    )
    parser.add_argument(
        '--rollback',
        metavar='BACKUP',
        help='restore files from a saved backup in .wallz-backups',
    )
    return parser.parse_args(argv)


def get_script_path():
    try:
        return os.path.abspath(__file__)
    except NameError:
        return os.path.abspath(sys.argv[0])


def hide_path(path):
    if sys.platform != 'win32':
        return

    try:
        import ctypes
        FILE_ATTRIBUTE_HIDDEN = 0x02
        ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        pass


def build_backup_dir(root_path):
    return os.path.join(root_path, BACKUP_DIR_NAME)


def write_backup_log(root_path, plan):
    root_path = os.path.abspath(root_path)
    backup_changes = []
    for item in plan:
        backup_changes.append({
            'directory': item['directory'],
            'directory_rel': os.path.relpath(item['directory'], root_path),
            'old_path': item['old_path'],
            'old_path_rel': os.path.relpath(item['old_path'], root_path),
            'new_path': item['new_path'],
            'new_path_rel': os.path.relpath(item['new_path'], root_path),
            'old_filename': item['old_filename'],
            'new_filename': item['new_filename'],
        })

    backup_data = {
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'root_path': root_path,
        'script_path': get_script_path(),
        'changes': backup_changes,
    }

    backup_dir = build_backup_dir(root_path)
    created = not os.path.exists(backup_dir)
    os.makedirs(backup_dir, exist_ok=True)
    if created:
        hide_path(backup_dir)
    filename = f"wallz_rename_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup_path = os.path.join(backup_dir, filename)

    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2)

    return backup_path


def group_changes_by_directory(changes):
    grouped = {}
    for item in changes:
        grouped.setdefault(item['directory'], []).append(item)
    return grouped


def apply_grouped_changes(changes, source_key, target_key, source_name_key, target_name_key, action_label):
    grouped = group_changes_by_directory(changes)

    total_renamed = 0
    total_dirs_processed = 0
    journal = []

    try:
        for directory, changes in grouped.items():
            # Rename through a temp folder so collisions do not break the run.
            temp_dir = os.path.join(directory, "_temp_rename_dir_")
            if os.path.exists(temp_dir):
                try:
                    for f in os.listdir(temp_dir):
                        os.remove(os.path.join(temp_dir, f))
                    os.rmdir(temp_dir)
                except Exception:
                    raise RuntimeError(f"Cannot clean up temporary directory {temp_dir}")
            
            os.mkdir(temp_dir)
            dir_renamed = 0
            print(f"\n{Colors.BOLD}{Colors.CYAN}Processing directory: {os.path.basename(directory)}{Colors.RESET}")

            try:
                for idx, item in enumerate(changes, start=1):
                    temp_name = item[source_name_key]
                    temp_path = os.path.join(temp_dir, f"{idx:06d}_{temp_name}")
                    shutil.move(item[source_key], temp_path)
                    item_journal = {
                        'source_path': item[source_key],
                        'temp_path': temp_path,
                        'target_path': item[target_key],
                    }
                    journal.append(item_journal)

                for item in changes:
                    journal_item = next(j for j in journal if j['source_path'] == item[source_key])
                    print(
                        f"  {Colors.GREEN}» {action_label}: "
                        f"{Colors.YELLOW}{item[source_name_key]} {Colors.RESET}➜ "
                        f"{Colors.BLUE}{item[target_name_key]}{Colors.RESET}"
                    )
                    shutil.move(journal_item['temp_path'], item[target_key])
                    dir_renamed += 1
                    total_renamed += 1

                os.rmdir(temp_dir)

                if dir_renamed > 0:
                    total_dirs_processed += 1

            except Exception:
                if os.path.exists(temp_dir):
                    pass
                raise

    except Exception:
        for item in changes:
            temp_dir = os.path.join(item['directory'], "_temp_rename_dir_")
            if os.path.exists(temp_dir):
                try:
                    if not os.listdir(temp_dir):
                        os.rmdir(temp_dir)
                except Exception:
                    pass

        raise

    return total_renamed, total_dirs_processed, journal


def rollback_from_journal(journal):
    print(f"\n{Colors.YELLOW}↩️ Rolling back changes...{Colors.RESET}")

    for item in reversed(journal):
        source_path = item['source_path']
        target_path = item['target_path']
        temp_path = item['temp_path']

        try:
            if os.path.exists(target_path) and not os.path.exists(source_path):
                shutil.move(target_path, source_path)
            elif os.path.exists(temp_path) and not os.path.exists(source_path):
                shutil.move(temp_path, source_path)
        except Exception as e:
            print(f"  {Colors.RED}[✗] Could not restore {os.path.basename(source_path)}: {e}{Colors.RESET}")

    print(f"{Colors.YELLOW}Rollback finished. Please check the folder if an error was shown above.{Colors.RESET}")


def apply_plan(root_path, plan, save_backup=False):
    if not plan:
        return 0, 0, None

    backup_path = None
    if save_backup:
        backup_path = write_backup_log(root_path, plan)

    total_renamed = 0
    total_dirs_processed = 0
    journal = []
    try:
        total_renamed, total_dirs_processed, journal = apply_grouped_changes(
            plan,
            'old_path',
            'new_path',
            'old_filename',
            'new_filename',
            'Renaming',
        )
    except Exception as e:
        print(f"\n{Colors.RED}[✗] Error: {e}{Colors.RESET}")
        rollback_from_journal(journal)
        print(f"\n{Colors.RED}[✗] Stopped. Your files were restored as much as possible.{Colors.RESET}")
        return total_renamed, total_dirs_processed, backup_path

    return total_renamed, total_dirs_processed, backup_path


def load_backup_file(backup_path):
    if not os.path.isfile(backup_path):
        raise FileNotFoundError(f'Backup file not found: {backup_path}')

    with open(backup_path, 'r', encoding='utf-8') as f:
        backup_data = json.load(f)

    if not isinstance(backup_data, dict) or 'changes' not in backup_data:
        raise ValueError('Invalid backup file.')

    changes = backup_data.get('changes')
    if not isinstance(changes, list):
        raise ValueError('Invalid backup file.')

    return backup_data


def resolve_backup_root(backup_path, backup_data):
    backup_dir = os.path.abspath(os.path.dirname(backup_path))
    current_root = os.path.abspath(os.path.dirname(backup_dir))
    saved_root = os.path.abspath(backup_data.get('root_path', current_root))

    if os.path.basename(backup_dir) != BACKUP_DIR_NAME:
        # Backup file was moved elsewhere, so fall back to the saved root.
        return saved_root

    return current_root


def extract_wallpaper_label(filename):
    match = re.match(r'^\d+\.\s(.+?)(\.[^.]+)$', filename)
    if not match:
        return None
    return match.group(1)


def restore_directory_name(directory, current_name, saved_name):
    current_dir = os.path.abspath(directory)
    current_basename = os.path.basename(current_dir)

    if not current_name or not saved_name or current_name == saved_name:
        return current_dir
    if current_basename != current_name:
        return current_dir

    target_dir = os.path.join(os.path.dirname(current_dir), saved_name)
    if os.path.exists(target_dir):
        raise RuntimeError(f"Cannot restore folder name because {target_dir} already exists")

    print(
        f"\n{Colors.BOLD}{Colors.CYAN}Restoring folder:{Colors.RESET} "
        f"{Colors.YELLOW}{current_name}{Colors.RESET} ➜ {Colors.BLUE}{saved_name}{Colors.RESET}"
    )
    shutil.move(current_dir, target_dir)
    return target_dir


def restore_directory_names_from_backup(changes, root_path):
    grouped = {}
    for item in changes:
        if 'directory_rel' in item:
            directory = os.path.join(root_path, item['directory_rel'])
        else:
            directory = item['directory']
        grouped.setdefault(directory, []).append(item)

    restored_dirs = {}
    for directory, items in grouped.items():
        current_labels = {extract_wallpaper_label(item['new_filename']) for item in items}
        saved_labels = {extract_wallpaper_label(item['old_filename']) for item in items}
        current_labels.discard(None)
        saved_labels.discard(None)

        if len(current_labels) == 1 and len(saved_labels) == 1:
            current_name = next(iter(current_labels))
            saved_name = next(iter(saved_labels))
            restored_dirs[directory] = restore_directory_name(directory, current_name, saved_name)
        else:
            restored_dirs[directory] = os.path.abspath(directory)

    return restored_dirs


def rollback_backup_file(backup_path):
    backup_data = load_backup_file(backup_path)
    root_path = resolve_backup_root(backup_path, backup_data)
    changes = backup_data['changes']
    restored_dirs = restore_directory_names_from_backup(changes, root_path)

    rollback_changes = []
    for item in changes:
        if 'directory_rel' in item:
            source_directory = os.path.join(root_path, item['directory_rel'])
        else:
            source_directory = item['directory']
        directory = restored_dirs.get(source_directory, os.path.abspath(source_directory))
        rollback_changes.append({
            'directory': directory,
            'old_path': os.path.join(directory, item['new_filename']),
            'new_path': os.path.join(directory, item['old_filename']),
            'old_filename': item['new_filename'],
            'new_filename': item['old_filename'],
        })

    total_restored = 0
    total_dirs_processed = 0
    journal = []
    try:
        total_restored, total_dirs_processed, journal = apply_grouped_changes(
            rollback_changes,
            'old_path',
            'new_path',
            'old_filename',
            'new_filename',
            'Restoring',
        )
    except Exception as e:
        print(f"\n{Colors.RED}[✗] Error: {e}{Colors.RESET}")
        rollback_from_journal(journal)
        print(f"\n{Colors.RED}[✗] Rollback stopped. Files were restored as much as possible.{Colors.RESET}")
        return total_restored, total_dirs_processed

    return total_restored, total_dirs_processed


# -----------------------------
# Main flow
# -----------------------------
def rename_wallpapers(root_path=None, save_backup=False, interactive=True):
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except:
            pass

    start_path = os.path.abspath(root_path or os.getcwd())

    if interactive:
        print(f"\n{Colors.BOLD}{Colors.CYAN}⛅ Wallz - Wallpaper Organizer{Colors.RESET}")
        print(f"{Colors.CYAN}{DIVIDER_55}{Colors.RESET}")
        print()
        print(f"{Colors.BLUE}📋 What this does:{Colors.RESET}")
        print(f"   • Finds images in your wallpaper folders")
        print(f"   • Lets you choose the folder to organize")
        print(f"   • Renames them: 01, 02, 03... + folder name")
        print(f"   • Example: random_pic.jpg → 01. Animated.jpg")
        print()
        print(f"{Colors.CYAN}{DIVIDER_55}{Colors.RESET}")
        print()

        print(f"{Colors.YELLOW}⚠️ Important: This script can rename a lot of files.{Colors.RESET}")
        print(f"{Colors.YELLOW}   Make sure this is the correct folder before continuing.{Colors.RESET}")
        print()
        
        print(f"{Colors.BOLD}Press Enter to continue or Ctrl+C to cancel.{Colors.RESET}")
        
        try:
            input()
        except KeyboardInterrupt:
            print("")
            print(f"\n{Colors.BLUE}{CANCELLED_MESSAGE}{Colors.RESET}")
            print("")
            return

    try:
        root_path = start_path
        if interactive and root_path == os.path.abspath(os.getcwd()):
            picker_path = root_path
            picker_selected_name = None
            picked_root_confirmed = False

            while True:
                if ask_folder_question(1, root_path):
                    break

                if LAST_VIEW_CONTEXT:
                    picker_path, picker_selected_name = LAST_VIEW_CONTEXT

                while True:
                    picked_path = pick_root_directory(picker_path, picker_selected_name)
                    if picked_path == PICKER_BACK_TO_QUESTION:
                        if LAST_VIEW_CONTEXT:
                            picker_path, picker_selected_name = LAST_VIEW_CONTEXT
                        break
                    if not picked_path:
                        print(f"\n{Colors.BLUE}{CANCELLED_MESSAGE}{Colors.RESET}")
                        return

                    if ask_folder_question(2, picked_path):
                        root_path = picked_path
                        picked_root_confirmed = True
                        break

                    picker_path, picker_selected_name = get_last_root_pick_context(picked_path)
                    print(f"{Colors.YELLOW}{CHOOSE_ANOTHER_FOLDER_MESSAGE}{Colors.RESET}")

                if picked_root_confirmed:
                    break
        elif interactive:
            if not ask_folder_question(1, root_path):
                print(f"\n{Colors.BLUE}{CANCELLED_MESSAGE}{Colors.RESET}")
                return

        if interactive and not confirm_continue():
            print(f"\n{Colors.BLUE}{CANCELLED_MESSAGE}{Colors.RESET}")
            return

        directories = get_target_directories(root_path)

        if not directories:
            print(f"\n{Colors.BLUE}{NO_CHANGES_HERE_MESSAGE}{Colors.RESET}")
            print("")
            return

        total_images_found = count_images_in_directories(directories)

        print()
        print(f"{Colors.CYAN}{DIVIDER_55}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}Renaming...{Colors.RESET}")
        print(f"{Colors.BLUE}Folders found:{Colors.RESET} {len(directories)}")
        print(f"{Colors.BLUE}Images found:{Colors.RESET} {total_images_found}")
        print(f"{Colors.CYAN}{DIVIDER_55}{Colors.RESET}")

        plan = build_full_plan(directories)

        if not plan:
            print(f"\n{Colors.BLUE}{ALREADY_NAMED_MESSAGE}{Colors.RESET}")
            print("")
            return

        total_renamed, total_dirs_processed, backup_path = apply_plan(
            root_path,
            plan,
            save_backup=save_backup,
        )
    
    except KeyboardInterrupt:
        print("")
        print(f"\n{Colors.BLUE}{CANCELLED_MESSAGE}{Colors.RESET}")
        print("")
        return
    
    if total_renamed > 0:
        print(f"\n{Colors.GREEN}[✓] Done! Renamed {Colors.BOLD}{total_renamed}{Colors.RESET}{Colors.GREEN} files across {Colors.BOLD}{total_dirs_processed}{Colors.RESET}{Colors.GREEN} directories.{Colors.RESET}")
        if backup_path:
            print(f"{Colors.BLUE}🧾 Backup log:{Colors.RESET} {backup_path}")
        print("")
    else:
        print(f"\n{Colors.BLUE}{ALREADY_NAMED_MESSAGE}{Colors.RESET}")
        print("")

if __name__ == "__main__":
    args = parse_args()

    if args.rollback:
        backup_file = os.path.abspath(args.rollback)
        try:
            restored, restored_dirs = rollback_backup_file(backup_file)
        except FileNotFoundError:
            print(f"\n{Colors.RED}[✗] Backup file not found.{Colors.RESET}")
            print(f"{Colors.YELLOW}{backup_file}{Colors.RESET}")
            print("")
            sys.exit(1)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"\n{Colors.RED}[✗] Invalid backup file.{Colors.RESET}")
            print(f"{Colors.YELLOW}{e}{Colors.RESET}")
            print("")
            sys.exit(1)
        except Exception as e:
            print(f"\n{Colors.RED}[✗] Rollback failed.{Colors.RESET}")
            print(f"{Colors.YELLOW}{e}{Colors.RESET}")
            print("")
            sys.exit(1)

        if restored > 0:
            print(
                f"\n{Colors.GREEN}[✓] Done! Restored {Colors.BOLD}{restored}{Colors.RESET}"
                f"{Colors.GREEN} files across {Colors.BOLD}{restored_dirs}{Colors.RESET}"
                f"{Colors.GREEN} directories.{Colors.RESET}"
            )
            print("")
        else:
            print(f"\n{Colors.BLUE}{ALREADY_NAMED_MESSAGE}{Colors.RESET}")
            print("")
    else:
        rename_wallpapers(
            root_path=os.path.abspath(args.root) if args.root else None,
            save_backup=args.save_backup,
            interactive=not args.yes,
        )
