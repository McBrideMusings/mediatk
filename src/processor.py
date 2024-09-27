import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import click
import ffmpeg
from .config import VidConfig

def process(input_file, vidconfig: VidConfig = None, duration: str = None) -> Path:
    """
    Process the input video file.

    Parameters:
    - input_file (str): Path to the input video file.
    - vidconfig (VidConfig, optional): Configuration settings.
    - duration (str, optional): Duration to process (e.g., '00:03:00' for 3 minutes).
                                 If None, processes the entire video.
    """
    click.echo(f"Processing {input_file}...")
    input_path = Path(input_file)
    output_filename = 'output_' + input_path.stem + '.' + (vidconfig.container or 'mp4')
    output_file = input_path.parent / output_filename

    vidconfig = vidconfig or VidConfig()

    # Probe the input file
    probe = ffmpeg.probe(input_file)

    # Determine video bit depth and set video filter
    input_bit_depth, vf_filter = determine_video_filter(probe)
    if input_bit_depth is None:
        click.echo("No video stream found in the input file.")
        return None

    # Include duration parameter in input if specified
    input_kwargs = {"hwaccel": "vaapi"}
    if duration:
        video_duration_str = probe['format']['duration']
        video_duration = float(video_duration_str)
        start_time = video_duration * 0.2  # Start at 20% into the video   
        input_kwargs['ss'] = start_time
        input_kwargs['t'] = duration

    input_stream = ffmpeg.input(input_file, **input_kwargs)

    # Initialize the streams list with the video stream
    streams = [input_stream.video]

    # Encoding parameters
    encoding_params = {
        'vf': vf_filter,
        'c:v': f"{vidconfig.video_codec}_vaapi",
    }

    # Include quality control if specified
    if vidconfig.video_quality is not None:
        if vidconfig.rc_mode is not 'CQP' and vidconfig.rc_mode is not 'VBR':
            click.echo(f"Unsupported rate control mode: {vidconfig.rc_mode}")
            return None
        # Set rate control mode
        encoding_params['rc_mode'] = vidconfig.rc_mode
        encoding_params['qp'] = vidconfig.video_quality 
        # if VBR, You can also specify maxrate and other parameters if desired
        click.echo(f"Using {'constant' if vidconfig.rc_mode == 'CQP' else 'variable'} QP mode with qp={vidconfig.video_quality}")
    else:
        click.echo("No video quality parameter specified. Using default encoding settings.")

    # Collect audio and subtitle streams
    ordered_audio_streams_info = collect_audio_streams(probe, input_stream, vidconfig)
    if not ordered_audio_streams_info:
        click.echo("No matching audio streams found in the input file.")
        return None

    # Extract the audio streams from the collected info
    ordered_audio_streams = [info['stream'] for info in ordered_audio_streams_info]
    ordered_subtitle_streams = collect_subtitle_streams(probe, input_stream, vidconfig)

    # Append the audio and subtitle streams to the streams list
    streams.extend(ordered_audio_streams)
    streams.extend(ordered_subtitle_streams)

    # Build the encoding parameters for audio streams
    for idx, info in enumerate(ordered_audio_streams_info):
        channels = info['channels']
        codec_name = info['codec_name']
        # Determine the desired output codec based on number of channels
        if channels > 2:
            desired_codec = 'ac3'
        else:
            desired_codec = 'aac'
        # Decide whether to copy or re-encode
        if codec_name == desired_codec:
            # Same codec, copy the stream
            encoding_params[f'c:a:{idx}'] = 'copy'
        else:
            # Re-encode the stream to the desired codec
            encoding_params[f'c:a:{idx}'] = desired_codec
            #encoding_params[f'ac:{idx}'] = channels  # Preserve the number of channels

    # Build the encoding parameters for subtitle streams
    for idx in range(len(ordered_subtitle_streams)):
        encoding_params[f'c:s:{idx}'] = 'copy'  # Copy subtitles

    # Include duration parameter in output if specified and not included in input
    output_kwargs = {}
    if duration and 't' not in input_kwargs:
        output_kwargs['t'] = duration

    # Set language metadata for audio streams
    metadata = {}
    for idx, subtitle in enumerate(vidconfig.language):
        metadata[f'metadata:s:a:{idx}'] = f'language={subtitle}'

    # Set language metadata for subtitle streams
    for idx, subtitle in enumerate(vidconfig.subtitles):
        metadata[f'metadata:s:s:{idx}'] = f'language={subtitle}'

    # Set disposition for audio streams
    # First audio stream is set as default; others are not
    disposition = {}
    for idx in range(len(ordered_audio_streams)):
        if idx == 0:
            disposition[f'disposition:a:{idx}'] = 'default'
        else:
            disposition[f'disposition:a:{idx}'] = '0'

    # Set disposition for subtitle streams (optional)
    for idx in range(len(ordered_subtitle_streams)):
        if idx == 0:
            disposition[f'disposition:s:{idx}'] = 'default'
        else:
            disposition[f'disposition:s:{idx}'] = '0'

    # Combine all parameters
    ffmpeg_params = {**encoding_params, **metadata, **disposition, **output_kwargs}

    # Run the ffmpeg command
    stream = ffmpeg.output(*streams, str(output_file), **ffmpeg_params)
    ffmpeg.run(stream, overwrite_output=True)
    return output_file


def determine_video_filter(probe: Dict) -> Tuple[Optional[int], str]:
    """Determine the input video's bit depth and set the appropriate video filter."""
    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    if video_stream is None:
        return None, ''

    input_pix_fmt = video_stream.get('pix_fmt', '')
    click.echo(f"Input pixel format: {input_pix_fmt}")

    pix_fmt_bit_depth = {
        'yuv420p': 8,
        'yuv422p': 8,
        'yuv444p': 8,
        'nv12': 8,
        'yuv420p10le': 10,
        'yuv422p10le': 10,
        'yuv444p10le': 10,
        'p010le': 10,
        'p210le': 10,
        'yuv420p12le': 12,
        'yuv422p12le': 12,
        'yuv444p12le': 12,
        'p016le': 16,
    }

    input_bit_depth = pix_fmt_bit_depth.get(input_pix_fmt, 8)  # Default to 8-bit if unknown

    if input_bit_depth > 8:
        vf_filter = "format=p010le,hwupload"
    else:
        vf_filter = "format=nv12,hwupload"

    return input_bit_depth, vf_filter


def collect_audio_streams(probe: Dict, input_stream, vidconfig: VidConfig) -> List[Dict]:
    """Collect and order audio streams based on the configuration."""
    audio_per_type_indices = {}
    audio_per_type_index = 0
    ordered_audio_streams = []

    # Build per-type indices for audio streams
    for stream in probe['streams']:
        if stream['codec_type'] == 'audio':
            audio_per_type_indices[stream['index']] = audio_per_type_index
            audio_per_type_index += 1

    # Collect audio streams
    for lang in vidconfig.language:
        found = False
        for stream in probe['streams']:
            if stream['codec_type'] == 'audio':
                stream_lang = stream.get('tags', {}).get('language', 'und')
                if stream_lang == lang:
                    index = stream['index']
                    per_type_index = audio_per_type_indices[index]
                    audio_stream = input_stream[f'a:{per_type_index}']
                    channels = stream.get('channels', 2)  # Default to 2 channels if not specified
                    codec_name = stream.get('codec_name', 'unknown')
                    ordered_audio_streams.append({
                        'stream': audio_stream,
                        'channels': channels,
                        'codec_name': codec_name,
                        'index': per_type_index
                    })
                    found = True
                    break
        if not found:
            click.echo(f"Warning: Audio stream with language '{lang}' not found.")
    return ordered_audio_streams

def collect_subtitle_streams(probe: Dict, input_stream, vidconfig: VidConfig) -> List:
    """Collect and order subtitle streams based on the configuration."""
    subtitle_per_type_indices = {}
    subtitle_per_type_index = 0
    ordered_subtitle_streams = []

    # Build per-type indices for subtitle streams
    for stream in probe['streams']:
        if stream['codec_type'] == 'subtitle':
            subtitle_per_type_indices[stream['index']] = subtitle_per_type_index
            subtitle_per_type_index += 1

    # Collect subtitle streams
    for lang in vidconfig.subtitles:
        for stream in probe['streams']:
            if stream['codec_type'] == 'subtitle':
                stream_lang = stream.get('tags', {}).get('language', 'und')
                if stream_lang == lang:
                    index = stream['index']
                    per_type_index = subtitle_per_type_indices[index]
                    subtitle_stream = input_stream[f's:{per_type_index}']
                    ordered_subtitle_streams.append(subtitle_stream)
    return ordered_subtitle_streams