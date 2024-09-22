from setuptools import setup, find_packages

setup(
    name='media_toolkit',
    version='1.0.0',
    packages=find_packages(),
    install_requires=[
        'click',
        'rarfile',
        'ffmpeg-python',
        'pyyaml'
    ],
    entry_points={
        'console_scripts': [
            'mediatk = src.cli:cli',
        ],
    },
)