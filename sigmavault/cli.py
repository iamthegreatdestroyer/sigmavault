"""
ΣVAULT CLI Module

This module provides the entry point for the sigmavault command-line interface.
It wraps the root-level CLI implementation for package distribution.
"""

import sys
import os

# Import the main function from the root CLI
def main():
    """Main entry point for the sigmavault CLI."""
    # Add parent directory to path to import root cli module
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    
    # Import and run the main CLI
    from cli import main as cli_main
    cli_main()


if __name__ == '__main__':
    main()
