#!/usr/bin/env python3

import os
import sys
import subprocess
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

def run_script(script_path: str, description: str) -> bool:
    """Run a Python script and return True if successful."""
    print(f"\n{Fore.CYAN}Running {description}...{Style.RESET_ALL}")
    try:
        result = subprocess.run([sys.executable, script_path], check=True)
        if result.returncode == 0:
            print(f"{Fore.GREEN}✓ {description} completed successfully{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}✗ {description} failed with return code {result.returncode}{Style.RESET_ALL}")
            return False
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}✗ {description} failed with error: {str(e)}{Style.RESET_ALL}")
        return False
    except Exception as e:
        print(f"{Fore.RED}✗ Error running {description}: {str(e)}{Style.RESET_ALL}")
        return False

def main():
    # Print welcome banner
    print("\n╭──────────────────���───────────────╮")
    print("│ Code Analysis Pipeline Runner    │")
    print("╰──────────────────────────────────╯")
    
    # Define script paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scripts = [
        {
            "path": os.path.join(base_dir, "main.py"),
            "description": "Part 1: File Path Collection"
        },
        {
            "path": os.path.join(base_dir, "summarize_files.py"),
            "description": "Part 2: File Summarization"
        },
        {
            "path": os.path.join(base_dir, "rag_query_tool", "query_interface.py"),
            "description": "Part 3: Interactive Query Interface"
        }
    ]
    
    # Run each script in sequence
    for script in scripts:
        print(f"\n{Fore.YELLOW}Starting {script['description']}{Style.RESET_ALL}")
        print("=" * 50)
        
        if not os.path.exists(script["path"]):
            print(f"{Fore.RED}✗ Script not found: {script['path']}{Style.RESET_ALL}")
            break
            
        success = run_script(script["path"], script["description"])
        if not success:
            print(f"\n{Fore.RED}Pipeline stopped due to error in {script['description']}{Style.RESET_ALL}")
            break
            
        print("=" * 50)
    
    print("\nPipeline execution completed.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Pipeline execution interrupted by user.{Style.RESET_ALL}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}Unexpected error: {str(e)}{Style.RESET_ALL}")
        sys.exit(1) 