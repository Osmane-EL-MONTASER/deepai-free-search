# Chat Service

My own chat service with real-time streaming powered by Ollama LLMs and ChromaDB vector storage. This chat service is a part of the deepai-free-search project. My goal at the end of this project is to mimic the new Deep Search Agent of OpenAI with open source tools. Keep in mind that this is a work in progress and I will update the project as I learn all these new tools.

[![Docker](https://img.shields.io/badge/Docker-✓-blue?logo=docker)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-✓-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/Ollama-✓-yellowgreen)](https://ollama.ai/)

## Features

- **Real-time Streaming**  
  Low-latency chat responses using Server-Sent Events (SSE)
- **Context-Aware Conversations**  
  ✨ *Coming Soon: Integrated ChromaDB vector store for contextual responses* ✨
- **Production-Ready**  
  Dockerized with health checks and configuration management
- **Scalable Architecture**  
  Asynchronous Python implementation with FastAPI

## Getting Started

### Prerequisites

- Docker

### Installation

1. Clone the repository

```bash
git clone https://github.com/Osmane-EL-MONTASER/deepai-free-search.git
cd deepai-free-search
```

2. Build and start the services

```bash
docker-compose up --build
```

3. Access the chat service

```bash
curl -X POST http://localhost:8000/chat/message -H "Content-Type: application/json" -d '{"messages": [{"role": "user", "content": "Hello, who are you? Nice to meet you!"}]}'
```


