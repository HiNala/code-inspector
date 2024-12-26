"""Module for generating code summaries using OpenAI."""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from colorama import init, Fore, Style
import openai
from dotenv import load_dotenv
from ..file_traversal.analyzer import CodeAnalyzer

# Initialize colorama
init()

# Load environment variables
load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Available models
MODELS = {
    "": {"name": "gpt-3.5-turbo", "display": "GPT-3.5 Turbo (Default)"},
    "1": {"name": "gpt-4", "display": "GPT-4"},
    "2": {"name": "gpt-4-turbo-preview", "display": "GPT-4 Turbo"},
    "3": {"name": "gpt-3.5-turbo", "display": "GPT-3.5 Turbo"},
}

def print_banner():
    """Print a welcome banner for the tool."""
    banner = """
╔════════════════════════════════════╗
║      File Content Summarizer       ║
╚════════════════════════════════════╝
"""
    print(f"{Fore.CYAN}{banner}{Style.RESET_ALL}")

def validate_openai_model(model_name: str) -> bool:
    """Validate that the OpenAI model exists and is accessible."""
    try:
        # Test the model with a simple request
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=5
        )
        print(f"\n{Fore.GREEN}✓ OpenAI model '{model_name}' validated successfully{Style.RESET_ALL}")
        print(f"Model details:")
        print(f"- ID: {response.id}")
        print(f"- Model: {response.model}")
        print(f"- Usage: {response.usage.total_tokens} tokens")
        return True
    except Exception as e:
        print(f"\n{Fore.RED}✗ Error validating OpenAI model: {str(e)}{Style.RESET_ALL}")
        return False

def select_model() -> str:
    """Prompt user to select an OpenAI model."""
    print(f"\n{Fore.GREEN}Available Models:{Style.RESET_ALL}")
    for key, model in MODELS.items():
        if key == "":
            print(f"Enter: {model['display']}")
        else:
            print(f"{key}: {model['display']}")
    
    while True:
        choice = input(f"\n{Fore.GREEN}Select a model (Enter for default, 1-3 for others): {Style.RESET_ALL}").strip()
        if choice in MODELS:
            model_name = MODELS[choice]["name"]
            if validate_openai_model(model_name):
                return model_name
            print(f"{Fore.RED}Please select a different model.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.{Style.RESET_ALL}")

def parse_text_paths(file_path: str) -> Tuple[List[str], Dict[str, int]]:
    """Extract file paths and statistics from plain text file."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.readlines()
    
    paths = []
    stats = {}
    
    # Parse the statistics section first
    in_stats = False
    for line in content:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("File Path Summary"):
            in_stats = True
            continue
            
        if in_stats and ":" in line and not line.startswith("-"):
            key, value = line.split(":", 1)
            try:
                stats[key.strip()] = int(value.strip())
            except ValueError:
                continue
        
        # Start collecting paths after the separator
        if "-" * 10 in line:
            in_stats = False
            continue
            
        if not in_stats and line and not line.startswith("-"):
            paths.append(line)
    
    if not paths:
        raise ValueError("Could not find file paths in the text file")
    
    return paths, stats

def analyze_paths(paths: List[str]) -> Tuple[Dict[str, List[str]], int, int, int]:
    """
    Analyze paths and return batches, counts of batches, single files, and empty folders.
    Returns (batches, batch_count, single_file_count, empty_folder_count)
    """
    batches = {}
    empty_folder_count = 0
    readme_count = 0
    
    # First pass: count empty folders and group by directory
    for path in paths:
        if "(empty folder)" in path:
            empty_folder_count += 1
            continue
            
        if os.path.basename(path).lower().startswith("readme."):
            readme_count += 1
            continue
            
        # Keep the full path structure
        directory = os.path.dirname(path)
        if directory:  # Only add if directory is not empty
            batches.setdefault(directory, []).append(path)
    
    # Count single files and clean up batches
    single_file_count = 0
    batch_count = 0
    
    # Create final batches dict with all files, preserving directory structure
    final_batches = {}
    for directory, files in batches.items():
        if len(files) == 1:
            single_file_count += 1
            final_batches[directory] = files  # Keep single files to maintain structure
        else:
            batch_count += 1
            final_batches[directory] = files
    
    return final_batches, batch_count, single_file_count, empty_folder_count

def show_spinner(duration: float):
    """Show a spinner animation for the specified duration."""
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    start_time = time.time()
    i = 0
    while (time.time() - start_time) < duration:
        print(f"\r{Fore.CYAN}{chars[i % len(chars)]} Processing...{Style.RESET_ALL}", end="", flush=True)
        i += 1
        time.sleep(0.1)

def summarize_file(file_path: str, model: str = "gpt-3.5-turbo", max_tokens: int = 1200) -> Tuple[str, Dict]:
    """
    Generate a detailed summary of a code file.
    
    Args:
        file_path: Path to the file to summarize
        model: OpenAI model to use
        max_tokens: Maximum tokens for the response
        
    Returns:
        Tuple containing the summary and token usage statistics
    """
    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Analyze the code
        analyzer = CodeAnalyzer()
        issues, stats = analyzer.analyze_file(file_path, content)
        analysis_results = {
            'stats': stats,
            'issues': issues
        }
        
        # Generate the prompt with analysis results
        prompt = generate_summary_prompt(file_path, content, analysis_results)
        
        # Get summary from OpenAI
        messages = [
            {
                "role": "system",
                "content": "You are a technical documentation expert that creates detailed and accurate code summaries."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.5,
            max_tokens=max_tokens
        )
        
        summary = response.choices[0].message.content
        usage = {
            'prompt_tokens': response.usage.prompt_tokens,
            'completion_tokens': response.usage.completion_tokens,
            'total_tokens': response.usage.total_tokens
        }
        
        return summary, usage
        
    except Exception as e:
        print(f"{Fore.RED}Error summarizing {file_path}: {str(e)}{Style.RESET_ALL}")
        return None, None

def save_summary(output_dir: str, file_path: str, summary: str, success: bool, usage_stats: dict = None):
    """Save the summary maintaining the original directory structure."""
    try:
        # Get the source root directory (up to 'src')
        src_index = file_path.lower().find('\\src\\')
        if src_index == -1:
            src_index = file_path.lower().find('/src/')
        
        if src_index != -1:
            # Extract the path after 'src'
            rel_path = file_path[src_index + 5:]  # +5 to skip '\src\'
        else:
            # Fallback to using the full path structure
            rel_path = file_path
        
        # Create the target directory structure
        target_dir = os.path.join(output_dir, os.path.dirname(rel_path))
        os.makedirs(target_dir, exist_ok=True)
        
        # Create the summary file with just .md extension
        summary_path = os.path.join(target_dir, f"{os.path.basename(file_path)}.md")
        
        print(f"\nSaving summary to: {summary_path}")  # Debug output
        
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(f"# Summary of {os.path.basename(file_path)}\n\n")
            f.write(f"Source: `{file_path}`\n\n")
            
            if success:
                if usage_stats:
                    f.write("## API Usage Stats\n")
                    f.write(f"- Model: `{usage_stats.get('model', 'N/A')}`\n")
                    f.write(f"- Total Tokens: `{usage_stats.get('total_tokens', 0)}`\n")
                    f.write(f"- Completion Tokens: `{usage_stats.get('completion_tokens', 0)}`\n")
                    f.write(f"- Prompt Tokens: `{usage_stats.get('prompt_tokens', 0)}`\n\n")
                f.write("## Summary\n\n")
                f.write(summary)
            else:
                f.write(f"## ❌ Error\n\n```\n{summary}\n```\n")
    except Exception as e:
        print(f"\n{Fore.RED}Error saving summary for {file_path}: {str(e)}{Style.RESET_ALL}")

def process_batch(batch_files: List[str], output_dir: str, model: str, batch_num: int, total_batches: int, one_by_one: bool = False):
    """Process a batch of files."""
    total_files = len(batch_files)
    successful = 0
    failed = 0
    total_tokens = 0
    
    print(f"\n{Fore.CYAN}Processing Batch {batch_num}/{total_batches} ({total_files} files){Style.RESET_ALL}")
    
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    for i, file_path in enumerate(batch_files, 1):
        if os.path.isfile(file_path):
            # Skip README files
            if os.path.basename(file_path).lower().startswith("readme."):
                continue
            
            if one_by_one:
                print(f"\nFile {i}/{total_files}: {file_path}")
                user_input = input("Press Enter to process this file (or 'q' to quit batch): ").strip().lower()
                if user_input == 'q':
                    print(f"{Fore.YELLOW}Skipping remaining files in batch.{Style.RESET_ALL}")
                    break
                
            progress = (i / total_files) * 100
            print(f"\r{Fore.CYAN}[{batch_num}/{total_batches}] Progress: {progress:.1f}%{Style.RESET_ALL} - Processing: {file_path}", end="", flush=True)
            
            try:
                summary, success, usage_stats = summarize_file(file_path, model)
                if success:
                    successful += 1
                    total_tokens += usage_stats.get('total_tokens', 0)
                else:
                    failed += 1
                    
                save_summary(output_dir, file_path, summary, success, usage_stats)
            except Exception as e:
                print(f"\n{Fore.RED}Error processing {file_path}: {str(e)}{Style.RESET_ALL}")
                failed += 1
            
            # Show a small spinner between API calls to avoid rate limits
            show_spinner(0.5)
    
    print(f"\n\nBatch {batch_num} Summary:")
    print(f"{Fore.GREEN}✓ Successful: {successful}{Style.RESET_ALL}")
    print(f"{Fore.RED}✗ Failed: {failed}{Style.RESET_ALL}")
    print(f"Total Tokens Used: {total_tokens}")
    return successful, failed, total_tokens

def get_latest_output_file() -> str:
    """Get the most recently created file in the output directory."""
    output_dir = "output"
    if not os.path.exists(output_dir):
        return None
        
    files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) 
             if f.startswith("file_paths_") and f.endswith(".txt")]
    
    if not files:
        return None
        
    return max(files, key=os.path.getctime)

def process_all_files(batches: Dict[str, List[str]], output_dir: str, model: str) -> Tuple[int, int, int]:
    """Process all files without batch prompts."""
    total_successful = 0
    total_failed = 0
    total_tokens = 0
    total_files = sum(len(files) for files in batches.values())
    processed = 0
    
    print(f"\n{Fore.CYAN}Processing all files ({total_files} total)...{Style.RESET_ALL}")
    
    for directory, files in batches.items():
        print(f"\n{Fore.YELLOW}Processing directory: {directory}{Style.RESET_ALL}")
        for file_path in files:
            if os.path.isfile(file_path):
                # Skip README files
                if os.path.basename(file_path).lower().startswith("readme."):
                    continue
                
                processed += 1
                progress = (processed / total_files) * 100
                print(f"\r{Fore.CYAN}Progress: {progress:.1f}%{Style.RESET_ALL} - Processing: {file_path}", end="", flush=True)
                
                try:
                    summary, success, usage_stats = summarize_file(file_path, model)
                    if success:
                        total_successful += 1
                        total_tokens += usage_stats.get('total_tokens', 0)
                    else:
                        total_failed += 1
                        
                    save_summary(output_dir, file_path, summary, success, usage_stats)
                except Exception as e:
                    print(f"\n{Fore.RED}Error processing {file_path}: {str(e)}{Style.RESET_ALL}")
                    total_failed += 1
                
                # Show a small spinner between API calls to avoid rate limits
                show_spinner(0.5)
    
    print(f"\n\n{Fore.GREEN}Processing Complete!{Style.RESET_ALL}")
    print(f"✓ Successful: {total_successful}")
    print(f"✗ Failed: {total_failed}")
    print(f"Total Tokens Used: {total_tokens}")
    
    return total_successful, total_failed, total_tokens

def generate_summary_prompt(file_path: str, content: str, analysis_results: Dict = None) -> str:
    """Generate a detailed prompt for the file summary."""
    prompt = f"""Analyze the following code file and provide a detailed summary.
File: {file_path}

Please structure the summary in the following sections:

1. Main Purpose
- Brief overview of the file's primary function and responsibility
- Key features or functionality provided

2. Technical Implementation
- Core classes, functions, or components
- Important algorithms or logic
- Design patterns used

3. Dependencies and Requirements
- External libraries and imports
- System requirements
- Configuration needs

4. Code Structure
- File organization
- Key sections and their purposes
- Important variables and constants

5. Usage Examples
- How to use the main functionality
- Example code snippets if applicable
- API endpoints or interfaces

6. Best Practices and Potential Improvements
- Areas following good practices
- Suggestions for improvement (only if deviating from best practices)
- Performance considerations

7. Code Analysis Results
"""

    if analysis_results:
        prompt += "\nStatic Analysis:\n"
        
        # Add code statistics
        stats = analysis_results.get('stats', {})
        if stats:
            prompt += "- Complexity Score: {}\n".format(stats.get('complexity', 'N/A'))
            prompt += "- Function Count: {}\n".format(stats.get('function_count', 'N/A'))
            prompt += "- Class Count: {}\n".format(stats.get('class_count', 'N/A'))
            prompt += "- Lines of Code: {}\n".format(stats.get('lines_of_code', 'N/A'))
            prompt += "- Comment Lines: {}\n".format(stats.get('comment_lines', 'N/A'))
            prompt += "- Maximum Nesting Depth: {}\n".format(stats.get('nesting_depth', 'N/A'))
        
        # Add identified issues
        issues = analysis_results.get('issues', [])
        if issues:
            prompt += "\nPotential Issues:\n"
            for issue in issues:
                prompt += f"- {issue}\n"
    
    prompt += f"\nCode Content:\n{content}\n"
    
    return prompt

def main():
    print_banner()
    
    # Create summaries directory if it doesn't exist
    summaries_dir = "summaries"
    if not os.path.exists(summaries_dir):
        os.makedirs(summaries_dir)
    
    # Select and validate model
    model = select_model()
    print(f"\nUsing model: {Fore.GREEN}{model}{Style.RESET_ALL}")
    
    # Try to find the latest output file
    latest_file = get_latest_output_file()
    if latest_file:
        print(f"\nFound latest file paths file: {Fore.CYAN}{latest_file}{Style.RESET_ALL}")
        use_latest = input(f"Use this file? (Y/n): ").strip().lower()
        if use_latest != 'n':
            paths_file = latest_file
        else:
            paths_file = input(f"\n{Fore.GREEN}Enter the path to the file paths file (e.g., output/file_paths_*.txt): {Style.RESET_ALL}").strip()
    else:
        paths_file = input(f"\n{Fore.GREEN}Enter the path to the file paths file (e.g., output/file_paths_*.txt): {Style.RESET_ALL}").strip()
    
    if not os.path.exists(paths_file):
        print(f"{Fore.RED}Error: Paths file not found.{Style.RESET_ALL}")
        return
    
    if not paths_file.endswith('.txt'):
        print(f"{Fore.RED}Error: File must be a text (.txt) file.{Style.RESET_ALL}")
        return
    
    # Parse and analyze file paths
    try:
        print(f"\n{Fore.CYAN}Analyzing paths...{Style.RESET_ALL}")
        paths, file_stats = parse_text_paths(paths_file)
        batches, batch_count, single_file_count, empty_folder_count = analyze_paths(paths)
        
        # Create output directory with timestamp inside summaries directory
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = os.path.join(summaries_dir, f"summary_{timestamp}")
        os.makedirs(output_dir, exist_ok=True)
        
        # Create a metadata file to store information about this run
        metadata_path = os.path.join(output_dir, "metadata.json")
        metadata = {
            "created_at": timestamp,
            "input_file": paths_file,
            "model": model,
            "statistics": file_stats,
            "analysis": {
                "total_files": len(paths),
                "batch_count": batch_count,
                "single_file_count": single_file_count,
                "empty_folder_count": empty_folder_count,
                "readme_count": sum(1 for p in paths if os.path.basename(p).lower().startswith('readme.'))
            }
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        # Print analysis results
        print(f"\nFile Statistics (from input file):")
        for key, value in file_stats.items():
            print(f"- {key}: {value}")
        
        print(f"\nAnalysis Results (current):")
        print(f"- Total Files Found: {len(paths)}")
        print(f"- Files to Process: {file_stats.get('Files to Process', 0)}")
        print(f"- Batches (multiple files): {batch_count}")
        print(f"- Single Files: {single_file_count}")
        print(f"- Empty Folders: {empty_folder_count}")
        print(f"- README Files: {sum(1 for p in paths if os.path.basename(p).lower().startswith('readme.'))}")
        
        if not batches:
            print(f"\n{Fore.YELLOW}No files found to summarize.{Style.RESET_ALL}")
            return
            
        # Ask user for processing mode
        print(f"\n{Fore.CYAN}Choose processing mode:{Style.RESET_ALL}")
        print("1. Process all files at once")
        print("2. Process files in batches (interactive)")
        
        while True:
            mode = input(f"\n{Fore.GREEN}Enter choice (1/2): {Style.RESET_ALL}").strip()
            if mode in ['1', '2']:
                break
            print(f"{Fore.RED}Invalid choice. Please enter 1 or 2.{Style.RESET_ALL}")
        
        # Process files according to chosen mode
        total_successful = 0
        total_failed = 0
        total_tokens_used = 0
        
        if mode == '1':
            # Process all files at once
            total_successful, total_failed, total_tokens_used = process_all_files(batches, output_dir, model)
        else:
            # Process in batches (interactive)
            print(f"\n{Fore.CYAN}Starting batch processing...{Style.RESET_ALL}")
            print(f"For each batch you can:")
            print(f"- Press Enter to process the entire batch")
            print(f"- Enter '1' to process files one by one")
            print(f"- Enter 'q' to quit")
            
            for i, (directory, files) in enumerate(batches.items(), 1):
                print(f"\n{Fore.YELLOW}Batch {i}/{len(batches)}: {directory}{Style.RESET_ALL}")
                print(f"Contains {len(files)} files")
                
                # Wait for user input
                user_input = input("Enter choice (Enter/1/q): ").strip().lower()
                if user_input == 'q':
                    print(f"\n{Fore.YELLOW}Processing stopped by user.{Style.RESET_ALL}")
                    break
                
                # Process batch according to user choice
                one_by_one = user_input == '1'
                successful, failed, tokens = process_batch(files, output_dir, model, i, len(batches), one_by_one)
                total_successful += successful
                total_failed += failed
                total_tokens_used += tokens
                
                if i < len(batches):
                    print(f"\n{Fore.CYAN}Waiting before next batch...{Style.RESET_ALL}")
                    show_spinner(2.0)
        
        # Update metadata with final statistics
        metadata["final_statistics"] = {
            "total_processed": total_successful + total_failed,
            "successful": total_successful,
            "failed": total_failed,
            "total_tokens_used": total_tokens_used,
            "processing_mode": "all_at_once" if mode == '1' else "batch_interactive"
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n{Fore.GREEN}Processing Complete!{Style.RESET_ALL}")
        print(f"\nFinal Statistics:")
        print(f"- Total Files Processed: {total_successful + total_failed}")
        print(f"- {Fore.GREEN}Successful: {total_successful}{Style.RESET_ALL}")
        print(f"- {Fore.RED}Failed: {total_failed}{Style.RESET_ALL}")
        print(f"- Total Tokens Used: {total_tokens_used}")
        print(f"\nSummaries saved to: {output_dir}")
            
    except Exception as e:
        print(f"{Fore.RED}Error analyzing paths: {e}{Style.RESET_ALL}")
        return

if __name__ == "__main__":
    main() 