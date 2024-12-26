#!/usr/bin/env python3

from src.file_traversal import get_file_paths
from src.output_handler import write_to_file
from colorama import init, Fore, Style
import os
import sys
import time

# Initialize colorama
init()

def print_banner():
    """Print a welcome banner for the tool."""
    banner = """
╔════════════════════════════════════╗
║     File Path Traversal Tool       ║
╚════════════════════════════════════╝
"""
    print(f"{Fore.CYAN}{banner}{Style.RESET_ALL}")

def main():
    """Main entry point for the file path traversal tool."""
    try:
        print_banner()
        
        # Get and validate input path
        root_path = input(f"{Fore.GREEN}Enter the root directory path:{Style.RESET_ALL} ").strip()
        
        if not os.path.exists(root_path):
            print(f"{Fore.RED}Error: The specified path does not exist.{Style.RESET_ALL}")
            sys.exit(1)
        
        if not os.path.isdir(root_path):
            print(f"{Fore.RED}Error: The specified path is not a directory.{Style.RESET_ALL}")
            sys.exit(1)
        
        # Show progress indicator
        print(f"\n{Fore.CYAN}Traversing the directory...{Style.RESET_ALL}")
        start_time = time.time()
        
        paths = get_file_paths(root_path)
        
        # Calculate and show execution time
        execution_time = time.time() - start_time
        print(f"Directory traversal completed in {execution_time:.2f} seconds")
        
        print(f"\n{Fore.CYAN}Writing paths to file...{Style.RESET_ALL}")
        output_file = write_to_file(paths)
        
        print(f"\n{Fore.GREEN}Success! File paths saved to: {Style.RESET_ALL}{output_file}")
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Operation cancelled by user.{Style.RESET_ALL}")
        sys.exit(1)
    except PermissionError as e:
        print(f"\n{Fore.RED}Permission denied: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}An error occurred: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)

if __name__ == "__main__":
    main() 