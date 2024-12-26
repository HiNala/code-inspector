"""Knowledge base for the RAG system with optimized performance."""

import os
import json
import faiss
import numpy as np
import tiktoken
from typing import List, Dict, Tuple, Optional, Generator
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import openai
from halo import Halo
from colorama import Fore, Style
import pickle
import shutil

# Load environment variables
load_dotenv()

# Constants
BATCH_SIZE = 10  # Number of files to process at once
MAX_CACHE_SIZE = 1000  # Maximum number of embeddings to cache
MAX_RETRIES = 3  # Maximum number of API call retries
EMBEDDING_DIMENSION = 1536  # Dimension of OpenAI embeddings
MAX_WORKERS = 4  # Maximum number of parallel workers

class KnowledgeBase:
    def __init__(self, model: str = "gpt-3.5-turbo"):
        """Initialize the knowledge base with performance optimizations."""
        self.model = model
        self.client = openai.OpenAI()
        self.index = None
        self.documents = []
        self.embeddings_cache = {}
        self.cache_lock = threading.Lock()
        self.embedding_model = "text-embedding-ada-002"
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
    def _batch_generator(self, items: List, batch_size: int) -> Generator[List, None, None]:
        """Generate batches of items for processing."""
        for i in range(0, len(items), batch_size):
            yield items[i:i + batch_size]
            
    def _manage_cache_size(self) -> None:
        """Ensure cache doesn't exceed maximum size."""
        with self.cache_lock:
            if len(self.embeddings_cache) > MAX_CACHE_SIZE:
                # Remove oldest 20% of cache entries
                num_to_remove = int(MAX_CACHE_SIZE * 0.2)
                for _ in range(num_to_remove):
                    self.embeddings_cache.popitem()
                    
    def _api_call_with_retry(self, func, *args, **kwargs) -> Dict:
        """Make API calls with retry logic."""
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                print(f"{Fore.YELLOW}Retry {attempt + 1}/{MAX_RETRIES}: {str(e)}{Style.RESET_ALL}")
                
    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text with caching."""
        cache_key = hash(text)
        with self.cache_lock:
            if cache_key in self.embeddings_cache:
                return self.embeddings_cache[cache_key]
                
        response = self._api_call_with_retry(
            self.client.embeddings.create,
            model=self.embedding_model,
            input=text
        )
        
        embedding = np.array(response.data[0].embedding, dtype=np.float32)
        
        with self.cache_lock:
            self.embeddings_cache[cache_key] = embedding
            self._manage_cache_size()
            
        return embedding
        
    def _process_batch_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Process a batch of texts to get embeddings."""
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(self._get_embedding, text) for text in texts]
            return [future.result() for future in as_completed(futures)]
            
    def initialize(self, summaries_dir: str) -> bool:
        """Initialize the knowledge base with batched processing."""
        try:
            # Load and validate summaries
            summaries_path = Path(summaries_dir)
            if not summaries_path.exists():
                raise FileNotFoundError(f"Directory not found: {summaries_dir}")
                
            summary_files = list(summaries_path.rglob("*.md"))
            if not summary_files:
                raise ValueError("No summary files found")
                
            # Initialize FAISS index
            self.index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
            total_files = len(summary_files)
            processed_files = 0
            
            with Halo(text='Processing summaries...', spinner='dots') as spinner:
                # Process files in batches
                for batch in self._batch_generator(summary_files, BATCH_SIZE):
                    batch_texts = []
                    batch_docs = []
                    
                    # Load batch content
                    for file_path in batch:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            batch_texts.append(content)
                            batch_docs.append({
                                'content': content,
                                'metadata': {
                                    'source_file': str(file_path),
                                    'created_at': file_path.stat().st_mtime
                                }
                            })
                            
                    # Get embeddings for batch
                    batch_embeddings = self._process_batch_embeddings(batch_texts)
                    
                    # Add to index and documents
                    self.index.add(np.vstack(batch_embeddings))
                    self.documents.extend(batch_docs)
                    
                    # Update progress
                    processed_files += len(batch)
                    spinner.text = f'Processed {processed_files}/{total_files} files'
                    
                spinner.succeed(f'Successfully processed {total_files} files')
                
            # Save index and cache
            self._save_state(summaries_dir)
            return True
            
        except Exception as e:
            print(f"{Fore.RED}Error initializing knowledge base: {str(e)}{Style.RESET_ALL}")
            return False
            
    def _save_state(self, base_dir: str) -> None:
        """Save index and cache state."""
        state_dir = Path(base_dir) / '.kb_state'
        state_dir.mkdir(exist_ok=True)
        
        # Save FAISS index
        faiss.write_index(self.index, str(state_dir / 'kb.index'))
        
        # Save documents and cache
        with open(state_dir / 'documents.pkl', 'wb') as f:
            pickle.dump(self.documents, f)
            
        with open(state_dir / 'cache.pkl', 'wb') as f:
            pickle.dump(self.embeddings_cache, f)
            
    def _load_state(self, base_dir: str) -> bool:
        """Load saved index and cache state."""
        try:
            state_dir = Path(base_dir) / '.kb_state'
            if not state_dir.exists():
                return False
                
            # Load FAISS index
            self.index = faiss.read_index(str(state_dir / 'kb.index'))
            
            # Load documents and cache
            with open(state_dir / 'documents.pkl', 'rb') as f:
                self.documents = pickle.load(f)
                
            with open(state_dir / 'cache.pkl', 'rb') as f:
                self.embeddings_cache = pickle.load(f)
                
            return True
            
        except Exception as e:
            print(f"{Fore.YELLOW}Could not load saved state: {str(e)}{Style.RESET_ALL}")
            return False
            
    def query(self, query: str, top_k: int = 5) -> Tuple[str, Dict]:
        """Query the knowledge base with optimized search."""
        try:
            # Get query embedding
            query_embedding = self._get_embedding(query)
            
            # Search index
            D, I = self.index.search(np.array([query_embedding]), top_k)
            
            # Get relevant documents
            results = []
            for idx in I[0]:
                if 0 <= idx < len(self.documents):
                    results.append(self.documents[idx])
                    
            # Format context
            context = self._format_context(results)
            
            # Get AI response
            response = self._get_ai_response(query, context)
            
            # Get token usage
            usage_stats = {
                'model': self.model,
                'total_tokens': len(self.tokenizer.encode(context + query + response)),
                'num_results': len(results)
            }
            
            return response, usage_stats
            
        except Exception as e:
            print(f"{Fore.RED}Error processing query: {str(e)}{Style.RESET_ALL}")
            raise
            
    def _format_context(self, results: List[Dict]) -> str:
        """Format search results into context."""
        context_parts = []
        for doc in results:
            metadata = doc['metadata']
            content = doc['content']
            context_parts.append(f"File: {metadata['source_file']}\n{content}\n---\n")
        return "\n".join(context_parts)
        
    def _get_ai_response(self, query: str, context: str) -> str:
        """Get AI response with retry logic."""
        response = self._api_call_with_retry(
            self.client.chat.completions.create,
            model=self.model,
            messages=[
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
                    "content": f"Context from codebase summaries:\n{context}\n\nQuestion: {query}"
                }
            ],
            temperature=0.7,
            max_tokens=800
        )
        
        return response.choices[0].message.content
        
    def cleanup(self) -> None:
        """Clean up resources."""
        # Clear cache
        self.embeddings_cache.clear()
        
        # Clear memory
        self.documents.clear()
        if self.index:
            self.index.reset()
            self.index = None 