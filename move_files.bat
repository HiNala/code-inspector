@echo off
echo Moving files to new locations...

:: Create directories if they don't exist
mkdir src\file_traversal 2>nul
mkdir src\summarizer 2>nul
mkdir src\rag 2>nul
mkdir src\rag\tts_stt 2>nul
mkdir tests 2>nul
mkdir output\file_paths 2>nul
mkdir output\summaries 2>nul
mkdir cache\tts 2>nul
mkdir cache\embeddings 2>nul
mkdir docs 2>nul

:: Move core files
copy src\file_traversal.py src\file_traversal\traversal.py
copy src\output_handler.py src\file_traversal\output.py
copy summarize_files.py src\summarizer\summarizer.py

:: Move RAG files
copy rag_query_tool\knowledge_base.py src\rag\
copy rag_query_tool\query_interface.py src\rag\
copy rag_query_tool\requirements.txt src\rag\
copy rag_query_tool\tts_stt\*.* src\rag\tts_stt\

:: Create empty __init__.py files
echo. > src\file_traversal\__init__.py
echo. > src\summarizer\__init__.py
echo. > src\rag\__init__.py
echo. > src\rag\tts_stt\__init__.py

echo File moves completed. 