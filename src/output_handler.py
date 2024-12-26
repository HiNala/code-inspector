"""Module for handling output operations."""

from datetime import datetime
from typing import List, Dict
import os
from colorama import init, Fore, Style

# Initialize colorama for console output only
init()

def write_to_file(paths_data: Dict) -> str:
    """
    Write the collected paths to a timestamped output file.
    
    Args:
        paths_data (Dict): Dictionary containing paths and statistics
        
    Returns:
        str: The name of the output file that was created.
    """
    # Create output directory if it doesn't exist
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = os.path.join(output_dir, f"file_paths_{timestamp}.txt")
    
    # Extract data
    all_paths = paths_data["all_paths"]
    empty_folders = paths_data["empty_folders"]
    readme_files = paths_data["readme_files"]
    stats = paths_data["stats"]
    
    # Group files by directory to count batches and single files
    batches = {}
    for path in all_paths:
        if path in empty_folders or path in readme_files:
            continue
        directory = os.path.dirname(path)
        batches.setdefault(directory, []).append(path)
    
    # Count single files and batches
    single_files = sum(1 for files in batches.values() if len(files) == 1)
    batch_count = sum(1 for files in batches.values() if len(files) > 1)
    
    # Write paths to file with summary
    with open(output_file, "w", encoding="utf-8") as f:
        # Write summary header
        f.write("File Path Summary\n")
        f.write("-" * 50 + "\n\n")
        
        # Write statistics
        f.write(f"Total Files Found: {stats['total_files']}\n")
        f.write(f"Files to Process: {stats['processed_files']}\n")
        f.write(f"Batches (multiple files): {batch_count}\n")
        f.write(f"Single Files: {single_files}\n")
        f.write(f"Empty Folders: {stats['empty_folders']}\n")
        f.write(f"README Files: {stats['readme_files']}\n")
        f.write("\n" + "-" * 50 + "\n\n")
        
        # Write paths in order: empty folders, READMEs, then all other files
        for path in empty_folders:
            f.write(f"{path}\n")
            
        for path in readme_files:
            f.write(f"{path}\n")
            
        for path in all_paths:
            if path not in empty_folders and path not in readme_files:
                f.write(f"{path}\n")
    
    # Print summary to console (keeping colors only for console output)
    print(f"\nSummary:")
    print(f"Total Files Found: {Fore.WHITE}{stats['total_files']}{Style.RESET_ALL}")
    print(f"Files to Process: {Fore.GREEN}{stats['processed_files']}{Style.RESET_ALL}")
    print(f"Batches (multiple files): {Fore.CYAN}{batch_count}{Style.RESET_ALL}")
    print(f"Single Files: {Fore.YELLOW}{single_files}{Style.RESET_ALL}")
    print(f"Empty Folders: {Fore.RED}{stats['empty_folders']}{Style.RESET_ALL}")
    print(f"README Files: {Fore.BLUE}{stats['readme_files']}{Style.RESET_ALL}")
    
    return output_file 