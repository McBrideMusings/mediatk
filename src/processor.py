import os
from pathlib import Path
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
    # Convert input_file to a Path object
    input_path = Path(input_file)
    
    # Construct the output file path with 'output_' prefix
    output_filename = 'output_' + input_path.name
    output_file = input_path.parent / output_filename

    vidconfig = vidconfig or VidConfig()

    # Probe the input file to get stream information
    probe = ffmpeg.probe(input_file)
 
    # Build mappings from global indices to per-type indices for audio and subtitle streams
    audio_per_type_indices = {}
    audio_per_type_index = 0
    subtitle_per_type_indices = {}
    subtitle_per_type_index = 0

    for stream in probe['streams']:
        if stream['codec_type'] == 'audio':
            audio_per_type_indices[stream['index']] = audio_per_type_index
            audio_per_type_index += 1
        elif stream['codec_type'] == 'subtitle':
            subtitle_per_type_indices[stream['index']] = subtitle_per_type_index
            subtitle_per_type_index += 1

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
        'vf': "format=p010le,hwupload",
        'c:v': f"{vidconfig.video_codec}_vaapi",
    }

    # Ordered lists for audio and subtitle streams
    ordered_audio_streams = []
    ordered_subtitle_streams = []

    # Collect and order audio streams
    for subtitle in vidconfig.language:
        found = False
        for stream in probe['streams']:
            if stream['codec_type'] == 'audio':
                stream_lang = stream.get('tags', {}).get('language', 'und')
                if stream_lang == subtitle:                    
                    index = stream['index']
                    per_type_index = audio_per_type_indices[index]
                    audio_stream = input_stream[f'a:{per_type_index}']
                    ordered_audio_streams.append(audio_stream)
                    found = True
                    break  # Stop after finding the first matching stream for this language
        if not found:
            click.echo(f"Warning: Audio stream with language '{subtitle}' not found.")

    if not ordered_audio_streams:
        click.echo("No matching audio streams found in the input file.")
        return None

    # Collect and order subtitle streams
    for subtitle in vidconfig.subtitles:
        for stream in probe['streams']:
            if stream['codec_type'] == 'subtitle':
                stream_lang = stream.get('tags', {}).get('language', 'und')
                if stream_lang == subtitle:
                    index = stream['index']
                    per_type_index = subtitle_per_type_indices[index]
                    subtitle_stream = input_stream[f's:{per_type_index}']
                    ordered_subtitle_streams.append(subtitle_stream)

    # Append the audio and subtitle streams to the streams list
    streams.extend(ordered_audio_streams)
    streams.extend(ordered_subtitle_streams)

    # Build the encoding parameters for audio streams
    for idx in range(len(ordered_audio_streams)):
        encoding_params[f'c:a:{idx}'] = vidconfig.audio_codec

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