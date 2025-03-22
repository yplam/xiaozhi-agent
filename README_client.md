# WebSocket Client for AI Agent Service

This client connects to a WebSocket server, sends a WAV file as audio data, receives the audio response, and saves it to a file.

## Prerequisites

- Python 3.10+
- `websockets` library
- A WAV file for testing
- Running AI agent WebSocket server

## Installation

1. Install the required packages:

```bash
pip install websockets
```

2. Make the script executable:

```bash
chmod +x client.py
```

## Usage

Basic usage:

```bash
./client.py --input your_input.wav --output response.opus
```

All available options:

```bash
./client.py --host 127.0.0.1 --port 8000 --input your_input.wav --output response.opus
```

### Arguments

- `--host`: WebSocket server host (default: 127.0.0.1)
- `--port`: WebSocket server port (default: 8000)
- `--input`: Path to input WAV file (required)
- `--output`: Path to save response audio (default: response.opus)

## Example

```bash
./client.py --input test_samples/hello.wav --output response.opus
```

## Note on Audio Formats

- The input must be a valid WAV file
- The output is saved in the format provided by the server (typically Opus)
- To play the output file, you can use a player that supports Opus format, such as VLC

## Troubleshooting

If you encounter issues:

1. Make sure the server is running and accessible
2. Check that your WAV file has the correct format (16000 Hz sample rate recommended)
3. Verify that the WebSocket protocol version matches the server's expected version
