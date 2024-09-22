from typing import List, Optional, Callable, TypeVar

T = TypeVar('T')

def save_to_file(data: str, output_file: str) -> None:
    with open(output_file, 'w') as file:
        file.write(data)

def save_array_to_file(video_paths: List[T], output_file: str, callback: Optional[Callable[[T], str]] = None) -> None:
    with open(output_file, 'w') as file:
        for path in video_paths:
            if callback is not None:
                file.write(f"{callback(path)}\n")
            else:
                file.write(f"{path}\n")

