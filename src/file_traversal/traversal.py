"""File traversal module for collecting and analyzing file paths."""

import os
from typing import Dict, List, Set
from .analyzer import CodeAnalyzer

def get_file_paths(root_path: str) -> Dict:
    """
    Traverse a directory and collect file information with analysis.
    
    Args:
        root_path (str): The root directory to start traversal from
        
    Returns:
        Dict containing:
        - paths: List of file paths
        - stats: Dictionary of statistics
        - analysis: Dictionary of file analysis results
    """
    paths = []
    stats = {
        'total_files': 0,
        'total_dirs': 0,
        'file_types': {},
        'largest_files': [],
        'deepest_nesting': 0
    }
    analysis_results = {}
    
    # Initialize analyzer
    analyzer = CodeAnalyzer()
    
    # Track unique directories
    unique_dirs = set()
    
    # Helper function to update file type stats
    def update_file_type_stats(file_path: str):
        ext = os.path.splitext(file_path)[1].lower()
        if ext:
            stats['file_types'][ext] = stats['file_types'].get(ext, 0) + 1
        else:
            stats['file_types']['no_extension'] = stats['file_types'].get('no_extension', 0) + 1
    
    # Helper function to track large files
    def track_large_file(file_path: str, size: int):
        stats['largest_files'].append((file_path, size))
        stats['largest_files'].sort(key=lambda x: x[1], reverse=True)
        stats['largest_files'] = stats['largest_files'][:5]  # Keep top 5
    
    for root, dirs, files in os.walk(root_path):
        # Update directory stats
        rel_path = os.path.relpath(root, root_path)
        nesting_level = len(rel_path.split(os.sep)) if rel_path != '.' else 0
        stats['deepest_nesting'] = max(stats['deepest_nesting'], nesting_level)
        
        # Add to unique directories
        unique_dirs.add(root)
        
        for file in files:
            file_path = os.path.join(root, file)
            rel_file_path = os.path.relpath(file_path, root_path)
            
            # Skip certain files and directories
            if any(part.startswith('.') for part in rel_file_path.split(os.sep)):
                continue
                
            # Get file info
            try:
                file_size = os.path.getsize(file_path)
                file_info = {
                    'path': rel_file_path,
                    'size': file_size,
                    'type': os.path.splitext(file)[1].lower(),
                    'nesting_level': nesting_level
                }
                
                # Analyze file content for code files
                if os.path.splitext(file)[1].lower() in ['.py', '.js', '.ts', '.tsx', '.jsx', '.cpp', '.c', '.h', '.java']:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            issues, code_stats = analyzer.analyze_file(file_path, content)
                            analysis_results[rel_file_path] = {
                                'issues': issues,
                                'stats': code_stats
                            }
                    except Exception as e:
                        analysis_results[rel_file_path] = {
                            'issues': [f"Error analyzing file: {str(e)}"],
                            'stats': {}
                        }
                
                paths.append(file_info)
                update_file_type_stats(file)
                track_large_file(rel_file_path, file_size)
                
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
                continue
    
    # Update final stats
    stats['total_files'] = len(paths)
    stats['total_dirs'] = len(unique_dirs)
    
    return {
        'paths': paths,
        'stats': stats,
        'analysis': analysis_results
    } 