# Code Analysis Pipeline

A comprehensive tool for analyzing codebases through file traversal, content summarization, and interactive querying.

## Features

- **File Path Collection**: Recursively traverse directories and collect file paths
- **Content Summarization**: Generate detailed summaries of code files using AI
- **Interactive Query Interface**: Query your codebase using natural language with voice support

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd file_path_tool
```

2. Install dependencies:
```bash
pip install -r requirements.txt
cd rag_query_tool
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and preferences
```

4. Run the complete pipeline:
```bash
python MASTER.py
```

Or run individual components:
```bash
python main.py              # File path collection
python summarize_files.py   # Content summarization
python rag_query_tool/query_interface.py  # Interactive querying
```

## Components

### 1. File Path Collection
- Traverses directories recursively
- Identifies empty folders
- Generates timestamped output files

### 2. Content Summarization
- Processes files in batches or all at once
- Skips README files automatically
- Creates mirrored directory structure for summaries
- Supports multiple OpenAI models

### 3. RAG Query Tool
- Natural language querying
- Voice input/output support
- Multiple TTS voices
- Response caching
- Offline fallback options

## Configuration

See `.env.example` for all available configuration options:
- OpenAI API settings
- ElevenLabs TTS configuration
- Speech recognition options
- Application preferences

## Requirements

- Python 3.8+
- OpenAI API key
- ElevenLabs API key (optional, for TTS)
- Google Cloud credentials (optional, for STT)

## Directory Structure

```
file_path_tool/
├── docs/               # Documentation
├── src/               # Core functionality
├── rag_query_tool/    # Query interface
├── summaries/         # Generated summaries
├── main.py           # File traversal script
├── summarize_files.py # Summarization script
└── MASTER.py         # Pipeline runner
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Your chosen license] 