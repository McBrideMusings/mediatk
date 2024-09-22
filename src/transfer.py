import os
import shutil
import rarfile

MEDIA_EXTENSIONS = {'.mp4', '.mp3', '.avi', '.mov', '.jpg', '.png', '.jpeg', '.mkv', '.flac', '.wav'}
RAR_EXTENSION = '.rar'

def is_media_file(file_name):
    """Check if the file is a media file based on the extension."""
    ext = os.path.splitext(file_name)[1].lower()
    return ext in MEDIA_EXTENSIONS

def is_rar_file(file_name):
    """Check if the file is a multi-part RAR file."""
    return file_name.lower().endswith(RAR_EXTENSION)

def extract_rar_file(rar_path, extract_to):
    """Extracts a RAR file to the specified directory."""
    try:
        with rarfile.RarFile(rar_path) as rf:
            print(f"Extracting {rar_path} to {extract_to}")
            rf.extractall(extract_to)
    except rarfile.Error as e:
        print(f"Error extracting {rar_path}: {e}")

def transfer_media_files(src_dir, dest_dir):
    """Recursively find media files and transfer them to the destination directory, including extracting RARs."""
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    
    for root, _, files in os.walk(src_dir):
        for file in files:
            src_file = os.path.join(root, file)
            
            if is_media_file(file):
                dest_file = os.path.join(dest_dir, file)
                print(f"Transferring {src_file} to {dest_file}")
                shutil.move(src_file, dest_file)
            
            elif is_rar_file(file):
                # Extract RAR file and scan the extracted contents
                extract_to = os.path.join(dest_dir, os.path.splitext(file)[0])
                extract_rar_file(src_file, extract_to)
                # Recursively scan the extracted files for more media files
                transfer_media_files(extract_to, dest_dir)