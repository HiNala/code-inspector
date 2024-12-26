#!/usr/bin/env python3

import os
import openai
from typing import List, Dict, Optional
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.live import Live
from knowledge_base import KnowledgeBase
from datetime import datetime
import json
from colorama import init, Fore, Style
import re
import keyboard
from tts_stt.speech_to_text import transcribe_speech_to_text
from tts_stt.text_to_speech import read_text_aloud, get_available_voices
import time

# Initialize colorama
init()

# Initialize rich console
console = Console()

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

# Global variables for voice selection
current_voice = "Bella"  # Default voice
voice_selection_active = False

def show_notification(message: str, style: str = "green") -> None:
    """Show a temporary notification at the top of the screen."""
    with console.status(f"[{style}]{message}[/]", spinner="dots") as status:
        time.sleep(1.5)

def create_voice_selection_table(voices: List[str], selected_idx: int = 0) -> Table:
    """Create a rich table for voice selection."""
    table = Table(title="Voice Selection", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Voice Name", style="cyan")
    table.add_column("Status", justify="right")
    
    for idx, voice in enumerate(voices):
        status = "► SELECTED" if idx == selected_idx else ""
        table.add_row(
            str(idx + 1),
            voice,
            status
        )
    return table

def select_voice() -> Optional[str]:
    """Display a voice selection panel and handle user input."""
    global current_voice, voice_selection_active
    
    if voice_selection_active:
        return None
        
    voice_selection_active = True
    available_voices = get_available_voices()
    
    if not available_voices:
        show_notification("No voices available", "red")
        voice_selection_active = False
        return None
    
    selected_idx = 0
    if current_voice in available_voices:
        selected_idx = available_voices.index(current_voice)
    
    # Create initial table
    table = create_voice_selection_table(available_voices, selected_idx)
    
    with Live(table, refresh_per_second=10) as live:
        while True:
            if keyboard.is_pressed('up'):
                selected_idx = (selected_idx - 1) % len(available_voices)
                table = create_voice_selection_table(available_voices, selected_idx)
                live.update(table)
                time.sleep(0.1)
            elif keyboard.is_pressed('down'):
                selected_idx = (selected_idx + 1) % len(available_voices)
                table = create_voice_selection_table(available_voices, selected_idx)
                live.update(table)
                time.sleep(0.1)
            elif keyboard.is_pressed('enter'):
                selected_voice = available_voices[selected_idx]
                if selected_voice != current_voice:
                    current_voice = selected_voice
                    show_notification(f"Voice changed to: {current_voice}")
                voice_selection_active = False
                return current_voice
            elif keyboard.is_pressed('esc'):
                voice_selection_active = False
                return None
            
            time.sleep(0.05)

def format_context(results: List[Dict]) -> str:
    """Format search results into context for the AI."""
    context = []
    for r in results:
        metadata = r['metadata']
        content = r['content']
        # Extract just the summary section for context
        summary_start = content.find("## Summary")
        if summary_start != -1:
            summary_content = content[summary_start:]
            context.append(f"File: {metadata['source_file']}\n{summary_content}\n---\n")
        else:
            context.append(f"File: {metadata['source_file']}\n{content}\n---\n")
    return "\n".join(context)

def get_ai_response(query: str, context: str) -> str:
    """Get AI response using OpenAI's API."""
    try:
        messages = [
            {
                "role": "system",
                "content": """You are a helpful assistant that answers questions about code based on file summaries.
                Use the provided context to answer questions accurately and concisely.
                If you're not sure about something, say so.
                Always reference the specific files you're drawing information from.
                Format your response in markdown for better readability."""
            },
            {
                "role": "user",
                "content": f"""Context from codebase summaries:
                {context}
                
                Question: {query}"""
            }
        ]
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=800
        )
        
        return response.choices[0].message.content
    except Exception as e:
        console.print(f"[red]Error getting AI response: {str(e)}[/]")
        return f"Error: Unable to generate response - {str(e)}"

def find_summary_directories() -> List[str]:
    """Find all summary directories in the summaries folder."""
    # Try multiple possible locations for the summaries directory
    possible_paths = [
        os.path.join("..", "summaries"),  # Relative path from rag_query_tool
        "summaries",  # Direct path
        os.path.abspath("summaries"),  # Absolute path
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "summaries")  # Path from script location
    ]
    
    summaries_dir = None
    for path in possible_paths:
        if os.path.exists(path) and os.path.isdir(path):
            summaries_dir = path
            break
            
    if not summaries_dir:
        return []
        
    # Get all directories that start with 'summary_'
    summary_dirs = [d for d in os.listdir(summaries_dir) 
                   if os.path.isdir(os.path.join(summaries_dir, d)) and d.startswith("summary_")]
    
    if not summary_dirs:
        return []
    
    # Sort by creation time, newest first
    summary_dirs.sort(key=lambda x: os.path.getctime(os.path.join(summaries_dir, x)), reverse=True)
    
    return [os.path.join(summaries_dir, d) for d in summary_dirs]

def select_summary_directory() -> Optional[str]:
    """Let user select a summary directory."""
    summary_dirs = find_summary_directories()
    
    if not summary_dirs:
        print(f"{Fore.RED}No summary directories found. Please run the summarizer first.{Style.RESET_ALL}")
        return None
        
    print(f"\n{Fore.GREEN}Found {len(summary_dirs)} summary directories:{Style.RESET_ALL}")
    for i, directory in enumerate(summary_dirs, 1):
        # Try to read metadata for more info
        metadata_path = os.path.join(directory, "metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                print(f"{i}. {os.path.basename(directory)}")
                print(f"   Created: {metadata.get('created_at', 'Unknown')}")
                print(f"   Model: {metadata.get('model', 'Unknown')}")
                if 'final_statistics' in metadata:
                    stats = metadata['final_statistics']
                    print(f"   Files: {stats.get('successful', 0)} successful, {stats.get('failed', 0)} failed")
            except:
                print(f"{i}. {os.path.basename(directory)}")
        else:
            print(f"{i}. {os.path.basename(directory)}")
    
    while True:
        choice = input(f"\n{Fore.GREEN}Select a directory (1-{len(summary_dirs)}, Enter for latest): {Style.RESET_ALL}").strip()
        if not choice:  # Default to the first (newest) directory
            return summary_dirs[0]
        try:
            index = int(choice) - 1
            if 0 <= index < len(summary_dirs):
                return summary_dirs[index]
        except ValueError:
            pass
        print(f"{Fore.RED}Invalid choice. Please try again.{Style.RESET_ALL}")

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
            return model_name
        print(f"{Fore.RED}Invalid choice. Please try again.{Style.RESET_ALL}")

def main():
    # Print welcome banner
    print("╭────────────────────────────────────────╮")
    print("│                                        │")
    print("│ ╔════════════════════════════════════╗ │")
    print("│ ║     Code Summary Query System      ║ │")
    print("│ ╚════════════════════════════════════╝ │")
    print("│                                        │")
    print("╰────────────────────────────────────────╯\n")
    
    # Initialize voice mode flags
    listening_mode = False
    last_response = None
    
    def toggle_listening_mode():
        nonlocal listening_mode
        listening_mode = True
        show_notification("Voice input activated")
    
    def read_last_response():
        nonlocal last_response
        if last_response:
            read_text_aloud(last_response, voice=current_voice)
        else:
            show_notification("No response to read", "yellow")
    
    # Register hotkeys
    keyboard.add_hotkey('ctrl+b', toggle_listening_mode)
    keyboard.add_hotkey('ctrl+n', read_last_response)
    keyboard.add_hotkey('ctrl+l', select_voice)
    
    # Select model
    model = select_model()
    print(f"\nUsing model: {Fore.GREEN}{model}{Style.RESET_ALL}")
    
    print("\nLooking for summary directories...")
    summary_dir = select_summary_directory()
    if not summary_dir:
        return
        
    # Initialize knowledge base with selected directory and model
    kb = KnowledgeBase(summary_dir, model)
    if not kb.initialize():
        print(f"{Fore.RED}Failed to initialize knowledge base.{Style.RESET_ALL}")
        return
        
    print(f"\n{Fore.GREEN}Knowledge base initialized successfully!{Style.RESET_ALL}")
    print(f"Using summaries from: {summary_dir}")
    print("\nFeatures available:")
    print("- Natural language queries")
    print("- Voice input (Ctrl+B)")
    print("- Text-to-speech output (Ctrl+N)")
    print("- Voice selection (Ctrl+L)")
    print("- Category-based search (use '@category:name' in query)")
    print("- Metadata filtering (use '#key:value' in query)")
    print("\nType 'quit' to exit, 'help' for more information")
    
    total_tokens = 0
    queries = 0
    
    while True:
        if listening_mode:
            # Voice input mode
            query = transcribe_speech_to_text()
            listening_mode = False
            if not query:  # If transcription failed or was cancelled
                continue
        else:
            # Text input mode
            query = input(f"\n{Fore.CYAN}Query [{queries + 1}]: {Style.RESET_ALL}").strip()
        
        if query.lower() in ['quit', 'exit', 'q']:
            break
            
        if query.lower() == 'help':
            print("\nQuery Examples:")
            print("- Basic: 'How does the authentication system work?'")
            print("- Category: '@components:What UI components handle forms?'")
            print("- Metadata: '#file_type:.tsx What components use hooks?'")
            print("- Combined: '@utils #created_after:2024-01-01 error handling'")
            print("\nVoice Commands:")
            print("- Ctrl+B: Start voice input")
            print("- Ctrl+N: Read last response aloud")
            print("- Ctrl+L: Select voice")
            print("\nSpecial Commands:")
            print("- 'quit' or 'q': Exit the program")
            print("- 'help': Show this help message")
            continue
            
        if not query:
            continue
            
        queries += 1
        
        # Parse category and metadata filters from query
        category = None
        filters = {}
        
        # Extract category (@category:query)
        category_match = re.match(r'@(\w+):(.*)', query)
        if category_match:
            category = category_match.group(1)
            query = category_match.group(2).strip()
        
        # Extract metadata filters (#key:value)
        filter_pattern = r'#(\w+):([^\s]+)'
        filter_matches = re.finditer(filter_pattern, query)
        for match in filter_matches:
            key, value = match.groups()
            filters[key] = value
            query = query.replace(match.group(0), '').strip()
        
        # Get response with expanded search
        response, usage_stats = kb.query(query)
        
        if response:
            print(f"\n{Fore.GREEN}Answer:{Style.RESET_ALL}")
            print(response)
            last_response = response  # Store response for TTS
            
            # Print usage statistics
            if usage_stats:
                total_tokens += usage_stats.get('total_tokens', 0)
                print(f"\n{Fore.YELLOW}Usage Statistics:{Style.RESET_ALL}")
                print(f"- Model: {usage_stats.get('model', 'Unknown')}")
                print(f"- Total Tokens: {usage_stats.get('total_tokens', 0)}")
                print(f"- Prompt Tokens: {usage_stats.get('prompt_tokens', 0)}")
                print(f"- Completion Tokens: {usage_stats.get('completion_tokens', 0)}")
                if usage_stats.get('expanded_search'):
                    print(f"- Expanded Search Terms: {usage_stats.get('num_expansions', 0)}")
        else:
            print(f"\n{Fore.RED}Sorry, I couldn't find relevant information to answer your question.{Style.RESET_ALL}")
            last_response = None
    
    # Print final statistics
    print("\nSession Summary:")
    print(f"- Total Queries: {queries}")
    print(f"- Total Tokens Used: {total_tokens}")
    print(f"- Average Tokens per Query: {total_tokens / queries if queries > 0 else 0:.1f}")
    print("\nThank you for using the Code Summary Query System!")

if __name__ == "__main__":
    main() 