from dataclasses import dataclass, field
from pathlib import Path
import yaml
import os
from typing import Dict, Any, List

config_name = "mediatk.yaml"


@dataclass
class VidConfig:
    container: str = 'mkv'
    video_codec: str = 'hevc'
    audio_codec: str = 'aac'
    language: List[str] = field(default_factory=lambda: ['eng', 'spa', 'esp'])
    subtitles: List[str] = field(default_factory=lambda: ['eng', 'spa', 'esp'])
    backup_dir: Path = Path('backup')

    def update_from_dict(self, config_dict: Dict[str, Any]):
        for key, value in config_dict.items():
            if hasattr(self, key):
                attr = getattr(self, key)

                if isinstance(attr, list):
                    # Ensure the value is a list
                    if not isinstance(value, list):
                        value = [value]
                    setattr(self, key, value)
                elif isinstance(attr, Path):
                    # Convert the value to a Path object if it's not already one
                    if not isinstance(value, Path):
                        value = Path(value)
                    setattr(self, key, value)
                else:
                    setattr(self, key, value)
            else:
                print(f"Warning: Unknown configuration option '{key}'")






def get_environment_config(path: str) -> Dict[str, Any]:
    """
    Load the configuration from a YAML file and merge it with the default configuration.

    Args:
        path (str): The path to the file to load the configuration from.

    Returns:
        Dict[str, Any]: The merged configuration.
    """
    env_config = VidConfig()
    env_files = find_all_yaml_configs(path)
    for env_file in env_files:
        override = parse_yaml_config(env_file)
        env_config.update_from_dict(override)
    return env_config
    

def find_all_yaml_configs(start_path: str) -> List[str]:
    """
    Search for all 'vidtk.yaml' files starting from the given path and moving up the directory tree.

    Args:
        start_path (str): The initial path to start the search from.

    Returns:
        List[str]: A list of paths to the found 'vidtk.yaml' files, ordered from root to the starting directory.
    """
    current_path = os.path.abspath(start_path)
    config_paths = []
    path_parts = current_path.split(os.sep)

    # Handle absolute paths that start with '/' (Unix) or 'C:\' (Windows)
    if os.name == 'nt' and path_parts[0].endswith(':'):
        # Windows absolute path, keep the drive letter
        root = path_parts[0]
        path_parts = [root] + path_parts[1:]
    elif path_parts[0] == '':
        # Unix absolute path, root is '/'
        path_parts[0] = os.sep

    # Build a list of directories from root to the current directory
    paths = []
    for i in range(1, len(path_parts) + 1):
        dir_path = os.path.join(*path_parts[:i])
        paths.append(dir_path)

    # Now search for 'vidtk.yaml' in each directory, starting from root
    for dir_path in paths:
        config_path = os.path.join(dir_path, config_name)
        if os.path.isfile(config_path):
            config_paths.append(config_path)

    return config_paths


def parse_yaml_config(file_path: str) -> Dict[str, Any]:
    """
    Parse a YAML configuration file and return a dictionary of parameters.
    
    Args:
        file_path (str): Path to the YAML configuration file.
    
    Returns:
        Dict[str, Any]: A dictionary containing the parsed configuration parameters.
    """
    try:
        with open(file_path, 'r') as config_file:
            config = yaml.safe_load(config_file)
        return config
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return {}
    except FileNotFoundError:
        print(f"Config file not found: {file_path}")
        return {}