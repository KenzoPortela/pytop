from .main import main
import curses

def run():
    """Entry point for the pytop command"""
    curses.wrapper(main)

__version__ = "1.0.0"