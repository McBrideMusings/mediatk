import os
from pathlib import Path
import subprocess
import ffmpeg
from typing import Callable, Dict, List, Optional
from typing import Tuple
from .config import VidConfig

# Define a list of common video file extensions
VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.mpeg', '.mpg']
VIDEO_EXTENSIONS_TO_CONTAINER = {
    'mp4': 'mpeg-4',
    'avi': 'avi',
    'mkv': 'matroska',
    'mov': 'quickTime',
    'wmv': 'windows media video',
    'flv': 'flash video',
    'webm': 'WebM',
    'mpeg': 'mpeg',
}

def find_videos(path: str, max_count: int = -1, filter_fn: Optional[Callable[[str], bool]] = None) -> List[str]:
    """
    Recursively searches for video files in the specified directory.

    Args:
        directory (str): The directory to search for video files.
        max_count (int, optional): The maximum number of video files to return. Defaults to -1, which means no limit.
        filter_fn (Optional[Callable[[str], bool]], optional): A function to filter video files. If None, no filtering is applied. Defaults to None.

    Returns:
        List[str]: A list of paths to the found video files.
    """
    video_files: List[str] = []

    path = Path(path)
    if path.is_file():
        if is_video_file(path):
            video_files.append(str(path))
        return video_files

    for root, dirs, files in os.walk(path):
        for file in files:
            if is_video_file(file):
                file_path = os.path.join(root, file)
                if filter_fn is None or filter_fn(file_path):
                    video_files.append(file_path)
                    if max_count > 0 and len(video_files) >= max_count:
                        return video_files
    return video_files

def is_video_file(file_path: str) -> bool:
    """
    Check if the specified file is a video file based on its extension.

    Args:
        file_path (str): The path to the file.

    Returns:
        bool: True if the file is a video file, False otherwise.
    """
    return any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)

def find_compilant_videos(directory: str, vidconfig: VidConfig, max_count: int = -1) -> List[str]:
    return find_videos(directory, max_count, lambda file: get_video_compliance(file, vidconfig)['overall'])

def is_video_file(file_path):
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv']  # Add more extensions as needed
    return file_path.is_file() and file_path.suffix.lower() in video_extensions

def is_video_compliant(input_file: str, vidconfig: VidConfig) -> bool:
    return get_video_compliance(input_file, vidconfig)['overall']

def get_video_compliance(input_file: str, vidconfig: VidConfig) -> Tuple[Dict[str, bool], Dict[str, str]]:
    """
    Check if the video file aligns with the specified configuration.

    Parameters:
    - input_file (str): Path to the input video file.
    - vidconfig (VidConfig): Configuration settings to check against.

    Returns:
    - Tuple[Dict[str, bool], Dict[str, str]]: A tuple containing a dictionary indicating compliance per property and overall compliance, and a dictionary with the actual properties of the video.
    """
    try:
        probe = ffmpeg.probe(input_file)
    except ffmpeg.Error as e:
        print(f"Error probing video file '{input_file}': {e}")
        return {'probe_error': False}, {}

    streams = probe.get('streams', [])
    format_info = probe.get('format', {})

    # Initialize variables to store the file's properties
    video_codecs = set()
    audio_codecs = set()
    subtitle_languages = set()
    format_names = format_info.get('format_name', '').split(',')

    # Extract information from streams
    for stream in streams:
        codec_type = stream.get('codec_type')
        codec_name = stream.get('codec_name')
        if codec_type == 'video':
            video_codecs.add(codec_name)
        elif codec_type == 'audio':
            audio_codecs.add(codec_name)
        elif codec_type == 'subtitle':
            tags = stream.get('tags', {})
            language = tags.get('language')
            if language:
                subtitle_languages.add(language)

    # Initialize compliance results
    compliance_results = {}
    compliance_results_verbose = {}

    # Check video codec
    video_codec_compliant = vidconfig.video_codec in video_codecs
    key = 'video_codec'
    compliance_results[key] = video_codec_compliant
    compliance_results_verbose[key] = f"{video_codecs}, expected '{vidconfig.video_codec}'"

    # Check audio codec
    audio_codec_compliant = vidconfig.audio_codec_stereo in audio_codecs or vidconfig.audio_codec_surround in audio_codecs
    key = 'audio_codec'
    compliance_results[key] = audio_codec_compliant
    compliance_results_verbose[key] = f"{audio_codecs}, expected '{vidconfig.audio_codec_stereo}' or '{vidconfig.audio_codec_surround}'"

    # Check subtitles
    missing_subtitles = [lang for lang in vidconfig.subtitles if lang not in subtitle_languages]
    extra_subtitles = len(subtitle_languages) > len(vidconfig.subtitles)
    subtitles_compliant = not missing_subtitles and not extra_subtitles
    key = 'subtitles'
    compliance_results[key] = subtitles_compliant
    compliance_results_verbose[key] = f"{subtitle_languages}, expected '{vidconfig.subtitles}'"

    # Check output format
    container = VIDEO_EXTENSIONS_TO_CONTAINER.get(vidconfig.container, vidconfig.container)
    format_compliant = container in format_names
    key = 'container'
    compliance_results[key] = format_compliant
    compliance_results_verbose[key] = f"{format_names}, expected '{container}'"

    # The overall compliance is True only if all specified properties are compliant
    if compliance_results:
        overall_compliance = all(compliance_results.values())
    else:
        # If no properties were checked, consider it compliant
        overall_compliance = True

    compliance_results['overall'] = overall_compliance
    compliance_results_verbose['overall'] = 'Compliant' if overall_compliance else 'Non-Compliant'
    return compliance_results, compliance_results_verbose


def print_video_compliance(input_file: str, vidconfig: VidConfig) -> str:
    """
    Print the compliance status of a video file based on the specified configuration.

    Parameters:
    - input_file (str): Path to the input video file.
    - vidconfig (VidConfig): Configuration settings to check against.

    Returns:
    - str: A formatted string indicating the compliance status.
    """
    compliance_results = get_video_compliance(input_file, vidconfig)

    # Prepare the output message
    output_lines = [
        f"File: {get_file_name(input_file)}",
        "Compliance Status:",
    ]

    for key, value in compliance_results.items():
        output_lines.append(f"  {key.replace('_', ' ').title()}: {'Compliant' if value else 'Non-Compliant'}")

    return '\n'.join(output_lines)


def prints_video_probes(video_files: List[str]) -> List[str]:
    results = []
    for file in video_files:
        results.append(print_video_probe(file))
    return results


def print_video_probe(video_file: str) -> str:
    codec = try_get_video_codec(video_file)
    return f"{get_file_name(video_file)}: {codec}"


# define a function that returns the file name
def get_file_name(file_path: str) -> str:
    return os.path.basename(file_path)


def try_get_video_codec(file_path: str) -> Optional[str]:
    # Use ffmpeg.probe to extract information about the file
    probe = ffmpeg.probe(file_path)
    
    # Extract the stream information that pertains to video
    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    
    if video_stream is None:
        raise ValueError("No video stream found in the file.")
    
    # Get the codec name
    codec_name = video_stream.get('codec_name', 'Unknown')
    
    return codec_name

def run_ffprobe(input_file):
    cmd = ['ffprobe', input_file]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return result.stdout

def probe_video(file_path) -> str:
    try:
        # Probe the file using ffmpeg.probe
        probe = ffmpeg.probe(file_path)
    except ffmpeg.Error as e:
        print(f"Error probing file: {e.stderr.decode()}")
        return

    # Initialize variables
    container = probe.get('format', {}).get('format_name', 'Unknown')
    bitrate = probe.get('format', {}).get('bit_rate', 'Unknown')

    # Initialize video and audio details
    video_codec = 'Unknown'
    resolution = 'Unknown'
    audio_codec = 'Unknown'
    audio_bitrate = 'Unknown'
    audio_language = 'Unknown'
    subtitle_tracks = []

    # Iterate over streams to find video, audio, and subtitle streams
    for stream in probe.get('streams', []):
        if stream.get('codec_type') == 'video' and video_codec == 'Unknown':
            video_codec = stream.get('codec_name', 'Unknown')
            width = stream.get('width')
            height = stream.get('height')
            if width and height:
                resolution = f"{width}x{height}"
        elif stream.get('codec_type') == 'audio' and audio_codec == 'Unknown':
            audio_codec = stream.get('codec_name', 'Unknown')
            audio_bitrate = stream.get('bit_rate', 'Unknown')
            audio_language = stream.get('tags', {}).get('language', 'Unknown')
        elif stream.get('codec_type') == 'subtitle':
            subtitle_language = stream.get('tags', {}).get('language', 'Unknown')
            subtitle_format = stream.get('codec_name', 'Unknown')
            subtitle_tracks.append({
                'language': subtitle_language,
                'format': subtitle_format
            })

    subtitle_track_count = len(subtitle_tracks)

    # Prepare the output
    output_lines = [
        f"Container: {container}",
        f"Video Codec: {video_codec}",
        f"Video Bitrate: {bitrate}",
        f"Audio Codec: {audio_codec}",
        f"Audio Bitrate: {audio_bitrate}",  
        f"Resolution: {resolution}", 
        f"Audio Language: {audio_language}",
        f"Subtitle Track Count: {subtitle_track_count}",
    ]

    for idx, subtitle in enumerate(subtitle_tracks, start=1):
        output_lines.append(f"Subtitle Track {idx}:")
        output_lines.append(f"  Language: {subtitle['language']}")
        output_lines.append(f"  Format: {subtitle['format']}")

    # Write output to a string
    return '\n'.join(output_lines)