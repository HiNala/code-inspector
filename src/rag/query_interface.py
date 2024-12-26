"""Interactive query interface for the RAG system."""

import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from colorama import init, Fore, Style
from .knowledge_base import KnowledgeBase
from .tts_stt.hotkeys import setup_voice_interface

# Initialize colorama
init()

class QueryInterface:
    def __init__(self, model: str = "gpt-3.5-turbo"):
        """Initialize query interface."""
        load_dotenv()
        
        self.kb = KnowledgeBase(model=model)
        self.voice_manager = None
        
        # Ensure OpenAI API key is set
        if not os.getenv("OPENAI_API_KEY"):
            print(f"{Fore.RED}Error: OPENAI_API_KEY not found in environment variables.{Style.RESET_ALL}")
            sys.exit(1)
            
    def initialize(self, summaries_dir: Optional[str] = None) -> bool:
        """Initialize knowledge base with summaries."""
        try:
            if not summaries_dir:
                summaries_dir = os.path.join(os.getcwd(), "summaries")
                
            if not os.path.exists(summaries_dir):
                print(f"{Fore.RED}Error: Summaries directory not found at {summaries_dir}")
                print("Please run the summarizer first.{Style.RESET_ALL}")
                return False
                
            print(f"\n{Fore.CYAN}Loading knowledge base...{Style.RESET_ALL}")
            self.kb.initialize(summaries_dir)
            return True
            
        except Exception as e:
            print(f"{Fore.RED}Error initializing knowledge base: {str(e)}{Style.RESET_ALL}")
            return False
            
    def _handle_query(self, query: str):
        """Process a query and handle the response."""
        try:
            response = self.kb.query(query)
            print(f"\n{Fore.GREEN}Assistant: {response}{Style.RESET_ALL}")
            
            if self.voice_manager:
                self.voice_manager.set_last_response(response)
                
        except Exception as e:
            print(f"{Fore.RED}Error processing query: {str(e)}{Style.RESET_ALL}")
            
    def run(self, use_voice: bool = False):
        """Run the interactive query interface."""
        print(f"\n{Fore.CYAN}Welcome to the Code Inspector Query Interface!")
        print("Type 'exit' or press Ctrl+C to quit.")
        print("Type 'voice' to toggle voice interface.")
        print(f"Current model: {self.kb.model}{Style.RESET_ALL}\n")
        
        try:
            while True:
                if use_voice and not self.voice_manager:
                    self.voice_manager = setup_voice_interface(callback=self._handle_query)
                    
                print(f"\n{Fore.YELLOW}Query: {Style.RESET_ALL}", end="")
                query = input().strip()
                
                if query.lower() == "exit":
                    break
                elif query.lower() == "voice":
                    use_voice = not use_voice
                    if use_voice:
                        if not self.voice_manager:
                            self.voice_manager = setup_voice_interface(callback=self._handle_query)
                        print(f"{Fore.CYAN}Voice interface enabled.{Style.RESET_ALL}")
                    else:
                        if self.voice_manager:
                            self.voice_manager.cleanup()
                            self.voice_manager = None
                        print(f"{Fore.CYAN}Voice interface disabled.{Style.RESET_ALL}")
                    continue
                    
                if query and not query.isspace():
                    self._handle_query(query)
                    
        except KeyboardInterrupt:
            print(f"\n{Fore.CYAN}Exiting...{Style.RESET_ALL}")
        finally:
            if self.voice_manager:
                self.voice_manager.cleanup()
                
def main():
    """Main entry point."""
    interface = QueryInterface()
    if interface.initialize():
        interface.run(use_voice=False)
        
if __name__ == "__main__":
    main() 