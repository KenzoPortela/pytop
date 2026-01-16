from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pytop",
    version="1.0.0",
    author="Kenzo Portela",
    author_email="portelakenzo@gmail.com",
    description="htop-like system monitor for Windows, written in Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kenzoportela/pytop",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
    ],
    python_requires=">=3.7",
    install_requires=[
        "psutil>=5.8.0",
        "WMI>=1.5.1",
        "windows-curses>=2.3.0",
    ],
    entry_points={
        "console_scripts": [
            "pytop=pytop:run",
        ],
    },
)