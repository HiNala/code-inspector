"""Module for traversing directories and collecting file paths."""

import os
from typing import List, Dict, Set
from rich.progress import Progress

def get_file_paths(root_path: str) -> Dict[str, List[str]]:
    """
    Traverse a directory and collect all file paths.
    Returns a dictionary with categorized paths and statistics.
    """
    all_paths: Set[str] = set()  # Use set to prevent duplicates
    empty_folders: List[str] = []
    readme_files: List[str] = []
    
    # Statistics
    stats = {
        "total_files": 0,
        "empty_folders": 0,
        "readme_files": 0,
        "processed_files": 0
    }
    
    # Count total items for progress bar
    total_items = sum([len(files) + len(dirs) for _, dirs, files in os.walk(root_path)])
    
    with Progress() as progress:
        task = progress.add_task("Progress:", total=total_items)
        
        for root, dirs, files in os.walk(root_path):
            # Update progress for current directory
            progress.update(task, advance=1)
            
            # Check if directory is empty
            if not dirs and not files:
                path = os.path.abspath(root)
                if path not in all_paths:
                    empty_folders.append(f"{path} (empty folder)")
                    all_paths.add(path)
                    stats["empty_folders"] += 1
                continue
            
            # Process files in current directory
            for file in files:
                progress.update(task, advance=1)
                
                file_path = os.path.abspath(os.path.join(root, file))
                
                # Skip if we've seen this path before
                if file_path in all_paths:
                    continue
                    
                all_paths.add(file_path)
                stats["total_files"] += 1
                
                # Track README files separately
                if file.lower().startswith("readme."):
                    readme_files.append(file_path)
                    stats["readme_files"] += 1
                else:
                    stats["processed_files"] += 1
    
    # Return both the paths and statistics
    return {
        "all_paths": sorted(list(all_paths)),  # Convert set back to sorted list
        "empty_folders": empty_folders,
        "readme_files": readme_files,
        "stats": stats
    } 