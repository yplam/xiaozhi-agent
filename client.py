#!/usr/bin/env python3
"""
WebSocket client for testing the AI agent service.

This script connects to a WebSocket server, sends a WAV file as audio data,
receives the audio response, and saves it to a file.
"""
import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import websockets
from websockets.exceptions import WebSocketException
from websockets.legacy.client import WebSocketClientProtocol

# Audio processing
import wave
import opuslib
import opuslib.api.encoder as opus
import array


class WebSocketClient:
    """
    WebSocket client for interacting with the AI agent service.
    """
    
    def __init__(
        self,
        server_host: str,
        server_port: int,
        client_id: str = "test_client",
        device_id: str = "test_device",
        protocol_version: int = 1
    ):
        """
        Initialize the WebSocket client.
        
        Args:
            server_host: WebSocket server host
            server_port: WebSocket server port
            client_id: Client identifier 
            device_id: Device identifier
            protocol_version: WebSocket protocol version
        """
        self.server_host = server_host
        self.server_port = server_port
        self.client_id = client_id
        self.device_id = device_id
        self.protocol_version = protocol_version
        
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.session_id: Optional[str] = None
        self.response_audio_data: List[bytes] = []
        self.tts_active = False
        
        print(f"WebSocket client initialized for {server_host}:{server_port}")
    
    async def connect(self) -> bool:
        """
        Connect to the WebSocket server.
        
        Returns:
            True if connected successfully, False otherwise
        """
        uri = f"ws://{self.server_host}:{self.server_port}"
        
        # Set headers for connection
        extra_headers = [
            ("Client-Id", self.client_id),
            ("Device-Id", self.device_id),
            ("Protocol-Version", str(self.protocol_version))
        ]
        
        try:
            # Use format compatible with websockets v15+
            self.websocket = await websockets.connect(
                uri, 
                additional_headers=extra_headers
            )
            print(f"Connected to {uri}")
            
            # Send hello message first
            await self._send_hello()
            
            # Wait for hello message from server
            hello_message = await self._wait_for_hello()
            if not hello_message:
                print("Failed to receive hello message from server")
                return False
            
            print(f"Received hello message: {hello_message}")
            
            # Store session ID if provided
            if "session_id" in hello_message:
                self.session_id = hello_message["session_id"]
                print(f"Session ID: {self.session_id}")
            
            return True
            
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    async def _send_hello(self) -> None:
        """Send a hello message to the server."""
        if not self.websocket:
            return
        
        # Format that matches the ProtocolParser.is_hello_message check:
        # message.get("type") == MessageType.HELLO and
        # message.get("transport") == "websocket" and
        # "audio_params" in message
        message = {
            "type": "hello",
            "transport": "websocket",
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60
            }
        }
        
        await self.websocket.send(json.dumps(message))
        print("Sent hello message to server")
    
    async def _wait_for_hello(self) -> Optional[Dict[str, Any]]:
        """
        Wait for the hello message from the server.
        
        Returns:
            Hello message or None if not received
        """
        if not self.websocket:
            return None
        
        try:
            # Set a timeout for receiving hello message
            data = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            
            message = json.loads(data)
            print(f"Received message: {message}")
            
            # Only check for 'type': 'hello' as the minimal requirement
            if message.get("type") == "hello":
                return message
            
            print(f"Unexpected message type: {message.get('type')}")
            return None
        except asyncio.TimeoutError:
            print("Timeout waiting for hello message")
            return None
        except Exception as e:
            print(f"Error waiting for hello message: {e}")
            return None
    
    def _encode_to_opus(self, pcm_data: bytes, channels: int, sample_rate: int) -> bytes:
        """
        Encode PCM audio data to Opus format.
        
        Args:
            pcm_data: PCM audio data
            channels: Number of audio channels
            sample_rate: Sample rate in Hz
            
        Returns:
            Opus-encoded audio data
        """
        # Create Opus encoder
        # Opus works with frame sizes that are multiples of 2.5ms
        # For 16kHz, this means 40 samples per 2.5ms
        # For 60ms frames, we need 960 samples (60/2.5 * 40)
        frame_size = int(sample_rate * 0.06)  # 60ms frame
        
        encoder = opus.create_state(
            fs=sample_rate,
            channels=channels,
            application=opuslib.APPLICATION_VOIP
        )
        
        # Convert bytes to array of 16-bit integers
        pcm_array = array.array('h')
        pcm_array.frombytes(pcm_data)
        
        # Encode in chunks
        opus_frames = []
        for i in range(0, len(pcm_array), frame_size):
            chunk = pcm_array[i:i+frame_size]
            # If last chunk is smaller than frame_size, pad with zeros
            if len(chunk) < frame_size:
                chunk.extend([0] * (frame_size - len(chunk)))
            
            # Convert array to bytes for encoder
            chunk_bytes = chunk.tobytes()
            
            # Encode to Opus - use module level function
            # Set max_data_bytes to accommodate the encoded data (typically smaller than input)
            max_data_bytes = len(chunk_bytes)
            encoded = opus.encode(encoder, chunk_bytes, frame_size, max_data_bytes)
            opus_frames.append(encoded)
        
        return b''.join(opus_frames)
    
    async def send_wav_file(self, wav_file_path: str) -> bool:
        """
        Send a WAV file to the server.
        
        Args:
            wav_file_path: Path to the WAV file
            
        Returns:
            True if the file was sent successfully, False otherwise
        """
        if not self.websocket:
            print("Not connected to server")
            return False
        
        try:
            # Open the WAV file and extract audio data
            with wave.open(wav_file_path, 'rb') as wav_file:
                # Get WAV file parameters
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                sample_rate = wav_file.getframerate()
                n_frames = wav_file.getnframes()
                
                print(f"WAV file: {wav_file_path}")
                print(f"Channels: {channels}, Sample width: {sample_width}")
                print(f"Sample rate: {sample_rate}, Frames: {n_frames}")
                
                # Start listening
                await self._send_listen_start()
                
                # Read audio data
                audio_data = wav_file.readframes(n_frames)
                
                # Create Opus encoder
                frame_size = int(sample_rate * 0.06)  # 60ms frame
                encoder = opus.create_state(
                    fs=sample_rate,
                    channels=channels,
                    application=opuslib.APPLICATION_VOIP
                )
                
                # Convert bytes to array of 16-bit integers
                pcm_array = array.array('h')
                pcm_array.frombytes(audio_data)
                
                # Encode and send in chunks
                frames_sent = 0
                for i in range(0, len(pcm_array), frame_size):
                    # Extract chunk
                    chunk = pcm_array[i:i+frame_size]
                    
                    # If last chunk is smaller than frame_size, pad with zeros
                    if len(chunk) < frame_size:
                        chunk.extend([0] * (frame_size - len(chunk)))
                    
                    # Convert array to bytes for encoder
                    chunk_bytes = chunk.tobytes()
                    
                    # Encode to Opus - use the module level function
                    # Set max_data_bytes to accommodate the encoded data
                    max_data_bytes = len(chunk_bytes)
                    encoded = opus.encode(encoder, chunk_bytes, frame_size, max_data_bytes)
                    
                    # Send the encoded frame
                    await self.websocket.send(encoded)
                    frames_sent += 1
                    
                    # Small delay to simulate real-time
                    await asyncio.sleep(0.05)
                
                print(f"Sent {frames_sent} Opus frames")
                
                # Stop listening
                await self._send_listen_stop()
                
                return True
                
        except Exception as e:
            print(f"Error sending WAV file: {e}")
            return False
    
    async def _send_listen_start(self) -> None:
        """Send a listen start message to the server."""
        if not self.websocket:
            return
        
        message = {
            "type": "listen",
            "state": "start",
            "mode": "manual"  # manual mode means we'll explicitly stop listening
        }
        
        await self.websocket.send(json.dumps(message))
        print("Sent listen start message")
    
    async def _send_listen_stop(self) -> None:
        """Send a listen stop message to the server."""
        if not self.websocket:
            return
        
        message = {
            "type": "listen",
            "state": "stop"
        }
        
        await self.websocket.send(json.dumps(message))
        print("Sent listen stop message")
    
    async def receive_response(self, timeout: int = 30) -> bool:
        """
        Receive and process the response from the server.
        
        Args:
            timeout: Maximum time to wait for a complete response in seconds
            
        Returns:
            True if a response was received, False otherwise
        """
        if not self.websocket:
            print("Not connected to server")
            return False
        
        # Clear previous response data
        self.response_audio_data = []
        self.tts_active = False
        
        try:
            # Set a timeout for the entire response
            start_time = asyncio.get_event_loop().time()
            
            while True:
                # Check if we've exceeded the timeout
                current_time = asyncio.get_event_loop().time()
                if current_time - start_time > timeout:
                    print(f"Response timeout after {timeout} seconds")
                    return len(self.response_audio_data) > 0
                
                # Wait for a message with a shorter timeout
                try:
                    data = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    print("No more messages from server")
                    return len(self.response_audio_data) > 0
                
                # Process the received data
                if isinstance(data, str):
                    # JSON message
                    message = json.loads(data)
                    message_type = message.get("type")
                    
                    print(f"Received message: {message_type}")
                    
                    if message_type == "tts":
                        state = message.get("state")
                        if state == "start":
                            print("TTS started")
                            self.tts_active = True
                        elif state == "stop":
                            print("TTS finished")
                            self.tts_active = False
                            # End of response
                            return len(self.response_audio_data) > 0
                        elif state == "sentence_start":
                            text = message.get("text", "")
                            print(f"TTS sentence: {text}")
                    
                    elif message_type == "stt":
                        text = message.get("text", "")
                        print(f"Transcription: {text}")
                    
                    elif message_type == "llm":
                        emotion = message.get("emotion", "neutral")
                        print(f"Emotion: {emotion}")
                    
                elif isinstance(data, bytes) and self.tts_active:
                    # Audio data
                    self.response_audio_data.append(data)
                    print(f"Received audio chunk: {len(data)} bytes")
                
        except Exception as e:
            print(f"Error receiving response: {e}")
            return False
    
    async def save_response_audio(self, output_path: str) -> bool:
        """
        Save the received audio response to a file.
        
        Args:
            output_path: Path to save the audio file
            
        Returns:
            True if the file was saved successfully, False otherwise
        """
        if not self.response_audio_data:
            print("No audio data to save")
            return False
        
        try:
            # Combine all audio chunks
            combined_audio = b''.join(self.response_audio_data)
            
            # Save the raw audio data
            with open(output_path, 'wb') as f:
                f.write(combined_audio)
            
            print(f"Saved audio response to {output_path}")
            return True
            
        except Exception as e:
            print(f"Error saving audio response: {e}")
            return False
    
    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            print("Connection closed")
            self.websocket = None


async def main() -> None:
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="WebSocket client for AI agent service")
    parser.add_argument("--host", default="127.0.0.1", help="WebSocket server host")
    parser.add_argument("--port", type=int, default=9005, help="WebSocket server port")
    parser.add_argument("--input", required=True, help="Path to input WAV file")
    parser.add_argument("--output", default="response.opus", help="Path to save response audio")
    args = parser.parse_args()
    
    # Create client
    client = WebSocketClient(args.host, args.port)
    
    try:
        # Connect to server
        if not await client.connect():
            print("Failed to connect to server")
            return
        
        # Send WAV file
        if not await client.send_wav_file(args.input):
            print("Failed to send WAV file")
            return
        
        # Receive response
        if not await client.receive_response():
            print("Failed to receive response")
            return
        
        # Save response audio
        await client.save_response_audio(args.output)
        
    finally:
        # Close connection
        await client.close()


if __name__ == "__main__":
    asyncio.run(main()) 