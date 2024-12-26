#!/usr/bin/env python3

import os
import json
import numpy as np
import faiss
from typing import List, Tuple, Dict
from openai import OpenAI
from colorama import init, Fore, Style
from dotenv import load_dotenv
import re
from halo import Halo
import tiktoken

# Initialize colorama
init(autoreset=True)

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Constants
EMBEDDING_MODEL = "text-embedding-ada-002"
EMBEDDING_CTX_LENGTH = 8191  # Maximum context length for text-embedding-ada-002

class KnowledgeBase:
    def __init__(self, summary_dir: str, model: str = "gpt-3.5-turbo"):
        self.summary_dir = summary_dir
        self.model = model
        self.client = OpenAI()
        self.index = None
        self.embeddings = None
        self.summaries = []
        self.metadata = {}
        self.embedding_tokens_used = 0
        self.enc = tiktoken.encoding_for_model(EMBEDDING_MODEL)
        
    def initialize(self) -> bool:
        """Initialize the knowledge base by loading summaries and building the search index."""
        try:
            # Load all summary files
            summary_files = []
            for root, _, files in os.walk(self.summary_dir):
                for file in files:
                    if file.endswith('.md'):
                        summary_files.append(os.path.join(root, file))
            
            if not summary_files:
                print(f"{Fore.RED}No summary files found in {self.summary_dir}{Style.RESET_ALL}")
                return False
            
            print(f"\nFound {len(summary_files)} summary files...")
            
            # Load summaries and metadata
            with Halo(text='Loading summaries...', spinner='dots') as spinner:
                for i, file_path in enumerate(summary_files, 1):
                    spinner.text = f"Loading summaries... ({i}/{len(summary_files)})"
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Extract metadata from the first line if it exists
                    lines = content.split('\n')
                    metadata = {}
                    if lines and lines[0].startswith('Original file:'):
                        original_file = lines[0].replace('Original file:', '').strip()
                        metadata['original_file'] = original_file
                        metadata['file_type'] = os.path.splitext(original_file)[1]
                        metadata['directory'] = os.path.dirname(original_file)
                        content = '\n'.join(lines[1:])
                    
                    self.summaries.append(content)
                    self.metadata[len(self.summaries) - 1] = metadata
                spinner.succeed("Summaries loaded successfully")
            
            # Generate embeddings
            print(f"\n{Fore.CYAN}Generating embeddings using {EMBEDDING_MODEL}...{Style.RESET_ALL}")
            texts = [self._preprocess_text(summary) for summary in self.summaries]
            
            with Halo(text='Processing embeddings...', spinner='dots') as spinner:
                self.embeddings = self._generate_embeddings(texts, spinner)
                if self.embeddings.size == 0:
                    return False
                spinner.succeed(f"Embeddings generated successfully (Used {self.embedding_tokens_used:,} tokens)")
            
            # Build FAISS index
            with Halo(text='Building search index...', spinner='dots') as spinner:
                self.index = faiss.IndexFlatL2(self.embeddings.shape[1])
                self.index.add(self.embeddings)
                spinner.succeed("Search index built successfully")
            
            print(f"\n{Fore.GREEN}Knowledge base initialized successfully!{Style.RESET_ALL}")
            print(f"Total embedding tokens used: {self.embedding_tokens_used:,}")
            return True
            
        except Exception as e:
            print(f"{Fore.RED}Error initializing knowledge base: {str(e)}{Style.RESET_ALL}")
            return False
    
    def query(self, query: str, category: str = None, filters: dict = None) -> Tuple[str, dict]:
        """
        Query the knowledge base with expanded search terms and metadata filtering.
        Returns the response and usage statistics.
        """
        try:
            # Expand search terms
            expanded_terms = self._expand_search_terms(query)
            expanded_query = ' '.join([query] + expanded_terms)
            
            # Generate query embedding
            query_embedding = self._generate_embeddings([self._preprocess_text(expanded_query)])
            
            # Search for relevant summaries
            k = min(5, len(self.summaries))  # Get top 5 results or all if less
            D, I = self.index.search(query_embedding, k)
            
            # Filter results by category and metadata
            filtered_indices = []
            for idx in I[0]:
                if idx < 0 or idx >= len(self.summaries):
                    continue
                    
                metadata = self.metadata.get(idx, {})
                
                # Apply category filter
                if category and not self._matches_category(metadata, category):
                    continue
                
                # Apply metadata filters
                if filters and not self._matches_filters(metadata, filters):
                    continue
                
                filtered_indices.append(idx)
            
            if not filtered_indices:
                return None, None
            
            # Prepare context from filtered summaries
            context = "\n\n---\n\n".join([self.summaries[i] for i in filtered_indices])
            
            # Generate response using ChatGPT
            messages = [
                {"role": "system", "content": "You are a helpful assistant that answers questions about code based on file summaries. "
                                           "Provide clear and concise answers, citing specific files when relevant."},
                {"role": "user", "content": f"Based on the following file summaries, please answer this question: {query}\n\nSummaries:\n{context}"}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.5,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content
            
            # Prepare usage statistics
            usage_stats = {
                'model': self.model,
                'total_tokens': response.usage.total_tokens,
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'expanded_search': bool(expanded_terms),
                'num_expansions': len(expanded_terms)
            }
            
            return answer, usage_stats
            
        except Exception as e:
            print(f"{Fore.RED}Error querying knowledge base: {str(e)}{Style.RESET_ALL}")
            return None, None
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for embedding generation."""
        # Remove markdown formatting
        text = re.sub(r'#+ ', '', text)  # Remove headers
        text = re.sub(r'\*\*|\*|~~|`', '', text)  # Remove bold, italic, strikethrough, code
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Replace links with text
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _generate_embeddings(self, texts: List[str], spinner: Halo) -> np.ndarray:
        """Generate embeddings for the given texts using OpenAI's embedding model."""
        try:
            embeddings = []
            total_texts = len(texts)
            
            for i, text in enumerate(texts, 1):
                # Count tokens
                tokens = self.enc.encode(text)
                self.embedding_tokens_used += len(tokens)
                
                # Update spinner with progress
                spinner.text = f"Processing embeddings... ({i}/{total_texts}) - {self.embedding_tokens_used:,} tokens used"
                
                # Check if text is too long
                if len(tokens) > EMBEDDING_CTX_LENGTH:
                    print(f"{Fore.YELLOW}Warning: Text too long ({len(tokens)} tokens), truncating to {EMBEDDING_CTX_LENGTH} tokens{Style.RESET_ALL}")
                    text = self.enc.decode(tokens[:EMBEDDING_CTX_LENGTH])
                
                response = self.client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=text
                )
                embeddings.append(response.data[0].embedding)
                
            return np.array(embeddings, dtype=np.float32)
        except Exception as e:
            print(f"{Fore.RED}Error generating embeddings: {str(e)}{Style.RESET_ALL}")
            return np.array([])
    
    def _expand_search_terms(self, query: str) -> List[str]:
        """Expand search terms using GPT to improve search coverage."""
        try:
            messages = [
                {"role": "system", "content": "You are a helpful assistant that generates related search terms. "
                                           "Provide 2-3 closely related alternative phrasings or technical terms."},
                {"role": "user", "content": f"Generate alternative search terms for: {query}"}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=100
            )
            
            expanded_terms = response.choices[0].message.content.split('\n')
            # Clean up terms (remove numbering, bullets, etc.)
            expanded_terms = [re.sub(r'^[\d\-\*\.\s]+', '', term).strip() for term in expanded_terms]
            expanded_terms = [term for term in expanded_terms if term and term != query]
            
            return expanded_terms
            
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not expand search terms: {str(e)}{Style.RESET_ALL}")
            return []
    
    def _matches_category(self, metadata: dict, category: str) -> bool:
        """Check if the summary matches the given category."""
        if not category:
            return True
            
        # Map category to metadata fields
        category_mappings = {
            'components': ['components', 'ui', 'interface'],
            'utils': ['utils', 'helpers', 'lib'],
            'api': ['api', 'endpoints', 'routes'],
            'config': ['config', 'settings', 'env'],
            'tests': ['tests', 'specs', '__tests__']
        }
        
        if category not in category_mappings:
            return True
            
        directory = metadata.get('directory', '').lower()
        return any(term in directory for term in category_mappings[category])
    
    def _matches_filters(self, metadata: dict, filters: dict) -> bool:
        """Check if the summary matches all the given filters."""
        if not filters:
            return True
            
        for key, value in filters.items():
            if key not in metadata:
                return False
            if metadata[key] != value:
                return False
        
        return True

if __name__ == "__main__":
    # Example usage
    kb = KnowledgeBase("summaries_2024-12-24_18-23-23")
    kb.build_index()
    results = kb.search("What components use toast notifications?")
    for r in results:
        print(f"\nFile: {r['metadata']['file_path']}")
        print(f"Distance: {r['distance']}")
        print("Content:", r['content'][:200], "...") 