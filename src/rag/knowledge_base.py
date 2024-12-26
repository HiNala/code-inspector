#!/usr/bin/env python3

import os
import json
import numpy as np
import faiss
from typing import List, Tuple, Dict, Generator
from openai import OpenAI
from colorama import init, Fore, Style
from dotenv import load_dotenv
import re
from halo import Halo
import tiktoken
from tqdm import tqdm
import time
from pathlib import Path
import hashlib

# Initialize colorama
init(autoreset=True)

# Load environment variables
load_dotenv()

# Constants
EMBEDDING_MODEL = "text-embedding-ada-002"
EMBEDDING_CTX_LENGTH = 8191
BATCH_SIZE = 10  # Number of files to process at once
MAX_RETRIES = 3  # Maximum number of API call retries
RETRY_DELAY = 2  # Seconds to wait between retries
MAX_CACHE_SIZE_GB = 2  # Maximum cache size in GB

class KnowledgeBase:
    def __init__(self, summary_dir: str, model: str = "gpt-3.5-turbo", cache_dir: str = "cache/embeddings"):
        self.summary_dir = summary_dir
        self.model = model
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = OpenAI()
        self.index = None
        self.embeddings = None
        self.summaries = []
        self.metadata = {}
        self.embedding_tokens_used = 0
        self.enc = tiktoken.encoding_for_model(EMBEDDING_MODEL)
        
    def _batch_generator(self, items: list, batch_size: int) -> Generator:
        """Generate batches of items."""
        for i in range(0, len(items), batch_size):
            yield items[i:i + batch_size]
            
    def _manage_cache_size(self):
        """Ensure cache directory doesn't exceed MAX_CACHE_SIZE_GB."""
        total_size = 0
        cache_files = []
        
        # Get all cache files with their sizes and timestamps
        for file in self.cache_dir.glob("*.npy"):
            stats = file.stat()
            total_size += stats.st_size
            cache_files.append((file, stats.st_mtime))
            
        # If cache exceeds limit, remove oldest files until under limit
        if total_size > MAX_CACHE_SIZE_GB * 1024**3:
            cache_files.sort(key=lambda x: x[1])  # Sort by modification time
            for file, _ in cache_files:
                file.unlink()
                total_size -= file.stat().st_size
                print(f"{Fore.YELLOW}Removed old cache file: {file.name}{Style.RESET_ALL}")
                if total_size <= MAX_CACHE_SIZE_GB * 1024**3:
                    break
                    
    def _api_call_with_retry(self, func, *args, **kwargs):
        """Make API calls with retry logic."""
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise e
                print(f"{Fore.YELLOW}API call failed, retrying in {RETRY_DELAY}s... ({attempt + 1}/{MAX_RETRIES}){Style.RESET_ALL}")
                time.sleep(RETRY_DELAY)

    def initialize(self) -> bool:
        """Initialize the knowledge base with improved memory management."""
        try:
            # Find all summary files
            summary_files = list(Path(self.summary_dir).rglob("*.md"))
            if not summary_files:
                print(f"{Fore.RED}No summary files found in {self.summary_dir}{Style.RESET_ALL}")
                return False
                
            print(f"\nFound {len(summary_files)} summary files...")
            
            # Process files in batches
            with tqdm(total=len(summary_files), desc="Loading summaries") as pbar:
                for batch in self._batch_generator(summary_files, BATCH_SIZE):
                    batch_summaries = []
                    batch_metadata = {}
                    
                    for file_path in batch:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        # Extract and store metadata
                        lines = content.split('\n')
                        metadata = self._extract_metadata(lines)
                        idx = len(self.summaries)
                        self.metadata[idx] = metadata
                        
                        # Store summary
                        summary = '\n'.join(lines[1:]) if metadata else content
                        self.summaries.append(summary)
                        batch_summaries.append(summary)
                        
                        pbar.update(1)
                        
                    # Generate embeddings for batch
                    if batch_summaries:
                        self._process_batch_embeddings(batch_summaries)
                        
            # Build FAISS index
            with Halo(text='Building search index...', spinner='dots') as spinner:
                if self.embeddings is None:
                    self.embeddings = np.concatenate([
                        np.load(f) for f in sorted(self.cache_dir.glob("*.npy"))
                    ])
                self.index = faiss.IndexFlatL2(self.embeddings.shape[1])
                self.index.add(self.embeddings)
                spinner.succeed("Search index built successfully")
                
            print(f"\n{Fore.GREEN}Knowledge base initialized successfully!{Style.RESET_ALL}")
            print(f"Total embedding tokens used: {self.embedding_tokens_used:,}")
            return True
            
        except Exception as e:
            print(f"{Fore.RED}Error initializing knowledge base: {str(e)}{Style.RESET_ALL}")
            return False
            
    def _process_batch_embeddings(self, texts: List[str]):
        """Process embeddings for a batch of texts with caching."""
        try:
            # Generate cache key for batch
            cache_key = hashlib.md5(''.join(texts).encode()).hexdigest()
            cache_file = self.cache_dir / f"emb_{cache_key}.npy"
            
            if cache_file.exists():
                # Load from cache
                batch_embeddings = np.load(cache_file)
            else:
                # Generate new embeddings
                processed_texts = [self._preprocess_text(text) for text in texts]
                embeddings = []
                
                for text in processed_texts:
                    tokens = self.enc.encode(text)
                    self.embedding_tokens_used += len(tokens)
                    
                    if len(tokens) > EMBEDDING_CTX_LENGTH:
                        text = self.enc.decode(tokens[:EMBEDDING_CTX_LENGTH])
                        
                    response = self._api_call_with_retry(
                        self.client.embeddings.create,
                        model=EMBEDDING_MODEL,
                        input=text
                    )
                    embeddings.append(response.data[0].embedding)
                    
                batch_embeddings = np.array(embeddings, dtype=np.float32)
                
                # Save to cache
                np.save(cache_file, batch_embeddings)
                self._manage_cache_size()
                
            # Append to main embeddings array
            if self.embeddings is None:
                self.embeddings = batch_embeddings
            else:
                self.embeddings = np.concatenate([self.embeddings, batch_embeddings])
                
        except Exception as e:
            print(f"{Fore.RED}Error processing batch embeddings: {str(e)}{Style.RESET_ALL}")
            raise e
    
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