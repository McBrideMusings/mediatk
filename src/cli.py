import os
from pathlib import Path
import click
from .config import VidConfig, get_environment_config
from .processor import *
from .scanner import *
from .transfer import *
from .utility import save_to_file

@click.group()
def cli():
    """A toolkit for video processing."""
    pass

@click.command() # prompt="enter path"
@click.argument('path', type=click.Path(exists=True))
@click.option("--cwd", is_flag=True, show_default=True, default=False, help="Write output in same folder")
@click.option("--until", default=20, help="Number of files to scan")
def scan(path, cwd, until):
    env_config = get_environment_config(path)
    until = until if until > 0 else 20
    result = find_videos(os.path.abspath(path), until, filter_fn=scan_filter)
    if len(result) == 0:
        click.echo("No video files found")
        return
    output_dir = path if not cwd else os.getcwd()
    click.echo(f"Found {len(result)} video files, outputting to {output_dir}")
    output_lines = []
    for index, file in enumerate(result):
        compliance, verbose_compliance = get_video_compliance(file, env_config)
        output_lines.append(f"Video {index}: {file}")
        for prop, is_compliant in compliance.items():
            line = f" - {prop}: {is_compliant} ({verbose_compliance[prop]})"
            output_lines.append(line)
        output_lines.append(f"")
        
    output_text = "\n".join(output_lines)
    output_file = f"ScanResults.txt"
    output_path = os.path.join(output_dir, output_file)
    save_to_file(output_text, output_path)
    click.echo(f"Saved video probe to {output_file}")

def scan_filter(file, env_config, only):
    if only and not file.endswith(only):
        return False
    return is_video_compliant(file, env_config)

@click.command() # prompt="enter path"
@click.argument('path', type=click.Path(exists=True))
@click.option("--cwd", is_flag=True, show_default=True, default=False, help="Write output in same folder")
@click.option("--until", default=20, help="Number of files to scan")
@click.option("--only", default="", help="Container format to scan")
def search(path, cwd, until, only):
    env_config = get_environment_config(path)
    until = until if until > 0 else 20
    result = find_videos(os.path.abspath(path), until, filter_fn=lambda x: x.endswith(only) if only else True)
    if len(result) == 0:
        click.echo("No video files found")
        return
    output_dir = path if not cwd else os.getcwd()
    click.echo(f"Found {len(result)} video files, outputting to {output_dir}")
    output_lines = []
    for index, file in enumerate(result):
        compliance, verbose_compliance = get_video_compliance(file, env_config)
        output_lines.append(f"Video {index}: {file}")
        for prop, is_compliant in compliance.items():
            line = f" - {prop}: {is_compliant} ({verbose_compliance[prop]})"
            output_lines.append(line)
        output_lines.append(f"")
        
    output_text = "\n".join(output_lines)
    output_file = f"ScanResults.txt"
    output_path = os.path.join(output_dir, output_file)
    save_to_file(output_text, output_path)
    click.echo(f"Saved video probe to {output_file}")

@click.command() # prompt="enter path"
@click.argument('path', type=click.Path(exists=True))
@click.option("--cwd", is_flag=True, show_default=True, default=False, help="Write output in same folder")
@click.option("--until", default=3, help="Number of files to scan")
def probe(path, cwd, until):
    until = until if until > 0 else 3
    path = Path(path)
    result = []
    if is_video_file(path):
        result = [str(path)]
    else:
        result = find_videos(os.path.abspath(path), until)

    if len(result) == 0:
        click.echo("No video files found")
        return
    output_dir = path if not cwd else os.getcwd()
    click.echo(f"Found {len(result)} video files, exporting to {output_dir}")
    for index, file in enumerate(result):
        export_probe(file)

@click.command("process") 
@click.argument('path', type=click.Path(exists=True))
@click.option("--count", default=-1, help="Number of files to scan")
@click.option("--compare", is_flag=True, show_default=True, default=False, help="Keep original files as they are")
def full_process(path, count, compare):
    env_config = get_environment_config(path)
    result = find_videos(os.path.abspath(path), count)
    click.echo(f"Found {len(result)} video files.")
    for file in result:
        input_path = Path(file)
        output_file = process(file, env_config)
        if compare:
            export_probe(file)
            export_probe(output_file)
            continue
            
        # Move the input file to the backup directory relative to the input file's directory
        backup_dir = input_path.parent / env_config.backup_dir
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / input_path.name
        shutil.move(str(input_path), str(backup_file))
        click.echo(f"Moved {input_path} to {backup_file}")
        
        # Rename the output file to the original input file's name
        final_output_file = input_path.parent / input_path.name
        output_file.rename(final_output_file)
        click.echo(f"Renamed {output_file} to {final_output_file}")

@click.command("sample") # prompt="enter path"
@click.argument('path', type=click.Path(exists=True))
@click.option("--until", default=1, help="Number of files to scan")
def sample_process(path, until):
    click.echo(f"Processing {path}")
    env_config = get_environment_config(path)
    result = find_videos(os.path.abspath(path), until)
    click.echo(f"Found {len(result)} video files.")
    for file in result:
        output_file = process(file, env_config, "00:00:10")
        click.echo(f"Processed {file} to {output_file}")


@click.command("config") # prompt="enter path"
@click.argument('path', type=click.Path(exists=True))
def print_config(path):
    env_config = get_environment_config(path)
    click.echo(env_config)


@click.command("transfer") # prompt="enter path"
@click.argument('src', type=click.Path(exists=True))
@click.argument('dest', type=click.Path(exists=True))
def transfer_media(src, dest):
    """Transfer all media files from SRC_DIR to DEST_DIR and handle RAR extraction."""
    click.echo(f"Transferring media files from {src} to {dest}")
    transfer_media_files(src, dest)

cli.add_command(transfer_media)
cli.add_command(print_config)
cli.add_command(probe)
cli.add_command(full_process)
cli.add_command(sample_process)
cli.add_command(scan)
cli.add_command(search)

def export_probe(file):
    video_info = run_ffprobe(file)
    output_file = f"Probe_{os.path.basename(file)}.txt"
    save_to_file(video_info, output_file)
    click.echo(f"Saved video probe to {output_file}")

if __name__ == '__main__':
    cli()