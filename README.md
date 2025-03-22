# Xiaozhi Agent

AI agent for ESP32 smart speakers using LangGraph with WebSocket communication.

## Features

- WebSocket server for client-server communication
- Speech recognition (ASR) for processing voice messages
- Text-to-speech (TTS) for generating voice responses
- LangGraph-based agent for smart processing
- OpenAI integration
- Extensible architecture for adding more node and tool types

## Setup

1. Ensure you have Python 3.10+ installed
2. Install Poetry for dependency management:

   ```
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. Install dependencies:

   ```
   poetry install
   ```

4. Create a `.env` file with your configuration:

   ```
   OPENAI_API_KEY=your_openai_api_key
   WS_PORT=8000
   PROXY_URL=http://your-proxy-if-needed
   ```

## Running the Server

```bash
poetry run python -m app.main
```

## Development

- Add new agent nodes in the `app/agent/nodes` directory
- Add new tools in the `app/agent/tools` directory
- Tests can be run with:

  ```
  poetry run pytest
  ```

## Protocol Documentation

The WebSocket protocol documentation can be found in:

- docs/websocket.md
- docs/server-websocket.md
- docs/client-websocket.md
