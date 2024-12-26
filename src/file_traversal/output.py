"""Output handling module for file traversal results."""

import os
import json
from datetime import datetime
from typing import Dict, List
from rich.console import Console
from rich.table import Table

console = Console()

def write_to_file(traversal_results: Dict) -> str:
    """
    Write traversal results to a file with detailed analysis.
    
    Args:
        traversal_results: Dictionary containing paths, stats, and analysis results
        
    Returns:
        str: Path to the output file
    """
    # Create output directory if it doesn't exist
    output_dir = os.path.join("output", "file_paths")
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = os.path.join(output_dir, f"file_paths_{timestamp}.txt")
    
    # Extract components
    paths = traversal_results['paths']
    stats = traversal_results['stats']
    analysis = traversal_results['analysis']
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write("=== File Path Analysis Report ===\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Write statistics
        f.write("=== Statistics ===\n")
        f.write(f"Total Files: {stats['total_files']}\n")
        f.write(f"Total Directories: {stats['total_dirs']}\n")
        f.write(f"Deepest Nesting Level: {stats['deepest_nesting']}\n\n")
        
        # Write file type distribution
        f.write("=== File Type Distribution ===\n")
        for ext, count in stats['file_types'].items():
            f.write(f"{ext}: {count} files\n")
        f.write("\n")
        
        # Write largest files
        f.write("=== Largest Files ===\n")
        for path, size in stats['largest_files']:
            size_mb = size / (1024 * 1024)
            f.write(f"{path}: {size_mb:.2f} MB\n")
        f.write("\n")
        
        # Write detailed file listing with analysis
        f.write("=== Detailed File Analysis ===\n")
        for file_info in sorted(paths, key=lambda x: x['path']):
            path = file_info['path']
            f.write(f"\nFile: {path}\n")
            f.write(f"Size: {file_info['size']} bytes\n")
            f.write(f"Type: {file_info['type']}\n")
            f.write(f"Nesting Level: {file_info['nesting_level']}\n")
            
            # Include code analysis if available
            if path in analysis:
                f.write("\nCode Analysis:\n")
                
                # Write code statistics
                stats = analysis[path]['stats']
                if stats:
                    f.write("  Statistics:\n")
                    f.write(f"  - Complexity: {stats.get('complexity', 'N/A')}\n")
                    f.write(f"  - Functions: {stats.get('function_count', 'N/A')}\n")
                    f.write(f"  - Classes: {stats.get('class_count', 'N/A')}\n")
                    f.write(f"  - Lines of Code: {stats.get('lines_of_code', 'N/A')}\n")
                    f.write(f"  - Comment Lines: {stats.get('comment_lines', 'N/A')}\n")
                    f.write(f"  - Nesting Depth: {stats.get('nesting_depth', 'N/A')}\n")
                
                # Write potential issues
                issues = analysis[path]['issues']
                if issues:
                    f.write("\n  Potential Issues:\n")
                    for issue in issues:
                        f.write(f"  - {issue}\n")
            
            f.write("\n" + "-"*50 + "\n")
    
    # Create a summary table for display
    table = Table(title="Analysis Summary")
    table.add_column("Category", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Files", str(stats['total_files']))
    table.add_row("Total Directories", str(stats['total_dirs']))
    table.add_row("Deepest Nesting", str(stats['deepest_nesting']))
    table.add_row("File Types", str(len(stats['file_types'])))
    
    # Count files with issues
    files_with_issues = sum(1 for file_analysis in analysis.values() if file_analysis['issues'])
    table.add_row("Files with Issues", str(files_with_issues))
    
    console.print(table)
    
    # Save metadata
    metadata = {
        'timestamp': timestamp,
        'stats': stats,
        'file_types': list(stats['file_types'].keys()),
        'analysis_summary': {
            'total_files_analyzed': len(analysis),
            'files_with_issues': files_with_issues
        }
    }
    
    metadata_file = os.path.join(output_dir, f"metadata_{timestamp}.json")
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    return output_file 