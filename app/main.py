"""
Main application module that connects the WebSocket server with the LangGraph agent.
"""
import asyncio
import json
import os
import signal
from typing import Any, Dict, List, Optional, Tuple

from app.agent.graph import AgentGraph
from app.config import WS_HOST, WS_PORT
from app.server.protocol import (AbortReason, ListenMode, ListenState,
                                MessageType, ProtocolMessage, ProtocolParser,
                                TTSState)
from app.server.websocket import WebSocketServer
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class Application:
    """
    Main application class that coordinates WebSocket server and LangGraph agent.
    """
    
    def __init__(self):
        """Initialize the application."""
        self.ws_server = WebSocketServer(WS_HOST, WS_PORT)
        self.agent_graph = AgentGraph()
        self.session_audio_buffers: Dict[str, List[bytes]] = {}
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.setup_handlers()
        logger.info("Application initialized")
    
    def setup_handlers(self) -> None:
        """Set up WebSocket event handlers."""
        self.ws_server.register_audio_handler(self.handle_audio)
        self.ws_server.register_message_handler(self.handle_message)
        self.ws_server.register_connect_handler(self.handle_connect)
        self.ws_server.register_disconnect_handler(self.handle_disconnect)
    
    async def handle_audio(self, session_id: str, audio_data: bytes) -> None:
        """
        Handle audio data from a client.
        
        Args:
            session_id: The client session ID
            audio_data: The opus-encoded audio data
        """
        # Initialize audio buffer for this session if it doesn't exist
        if session_id not in self.session_audio_buffers:
            self.session_audio_buffers[session_id] = []
        
        # Add audio data to buffer
        self.session_audio_buffers[session_id].append(audio_data)
        
        # Get the session info and check listening mode
        session_info = self.active_sessions.get(session_id, {})
        listen_mode = session_info.get("listen_mode")
        
        # If realtime mode or we have enough audio data in auto mode, process it
        if (listen_mode == ListenMode.REALTIME or 
            (listen_mode == ListenMode.AUTO and len(self.session_audio_buffers[session_id]) >= 10)):
            await self.process_audio_buffer(session_id)
    
    async def handle_message(self, session_id: str, message: Dict[str, Any]) -> None:
        """
        Handle a message from a client.
        
        Args:
            session_id: The client session ID
            message: The message
        """
        logger.info(f"Received message from {session_id}: {message}")
        
        message_type = message.get("type")
        
        if message_type == MessageType.LISTEN:
            # Handle listen message
            state = message.get("state")
            
            if state == ListenState.START:
                # Start listening
                mode = message.get("mode", ListenMode.AUTO)
                logger.info(f"Client {session_id} started listening in mode: {mode}")
                
                self.session_audio_buffers[session_id] = []
                self.active_sessions[session_id] = {
                    "listen_mode": mode,
                    "listening": True
                }
                
            elif state == ListenState.STOP:
                # Stop listening and process buffered audio
                logger.info(f"Client {session_id} stopped listening")
                if session_id in self.active_sessions:
                    self.active_sessions[session_id]["listening"] = False
                    
                # Process any remaining audio
                if session_id in self.session_audio_buffers and self.session_audio_buffers[session_id]:
                    await self.process_audio_buffer(session_id)
                    
            elif state == ListenState.DETECT:
                # Wake word detected
                wake_word = message.get("text", "")
                logger.info(f"Wake word detected from {session_id}: {wake_word}")
                
                # Process as direct text input if it came from text source
                if message.get("source") == "text":
                    # Instead of constructing a message, just pass the wake word directly
                    result = await self.agent_graph.process_text_input(wake_word, session_id)
                    await self.send_agent_response(session_id, result)
                else:
                    # Process audio if the wake word was detected from audio
                    if session_id in self.session_audio_buffers:
                        await self.process_audio_buffer(session_id, wake_word=wake_word)
        
        elif message_type == MessageType.ABORT:
            # Handle abort message
            logger.info(f"Abort message from {session_id}")
            reason = message.get("reason", AbortReason.USER_REQUESTED)
            
            # Clear any pending audio buffer
            if session_id in self.session_audio_buffers:
                self.session_audio_buffers[session_id] = []
            
            # Send TTS stop message
            await self.ws_server.send_message(
                session_id, 
                ProtocolMessage.create_tts_stop_message()
            )
        
        elif message_type == MessageType.IOT:
            # Handle IoT message
            if "descriptors" in message:
                logger.info(f"Received IoT descriptors from {session_id}")
                # Store device descriptors for this session
                if session_id not in self.active_sessions:
                    self.active_sessions[session_id] = {}
                self.active_sessions[session_id]["descriptors"] = message.get("descriptors", [])
                await self.agent_graph.process_message("iot", message, session_id)
                
            elif "states" in message:
                logger.info(f"Received IoT states from {session_id}")
                # Store device states for this session
                if session_id not in self.active_sessions:
                    self.active_sessions[session_id] = {}
                self.active_sessions[session_id]["states"] = message.get("states", {})
                await self.agent_graph.process_message("iot", message, session_id)
                
            elif "commands" in message:
                logger.info(f"Received IoT commands from {session_id}")
                await self.agent_graph.process_message("iot", message, session_id)
        
        elif message_type == MessageType.FUNCTION_CALL:
            # Handle function call message
            logger.info(f"Received function call from {session_id}")
            function_name = message.get("function", "")
            arguments = message.get("arguments", {})
            
            # Process the function call through the agent graph
            result = await self.agent_graph.process_function_call(
                function_name, arguments, session_id
            )
            
            await self.send_agent_response(session_id, result)
    
    async def handle_connect(self, session_id: str, client_id: str, device_id: str) -> None:
        """
        Handle a client connection.
        
        Args:
            session_id: The session ID
            client_id: The client ID
            device_id: The device ID
        """
        logger.info(f"Client connected: {session_id} (client: {client_id}, device: {device_id})")
        
        # Initialize session info
        self.active_sessions[session_id] = {
            "client_id": client_id,
            "device_id": device_id,
            "listening": False,
            "listen_mode": None
        }
        
        # Initialize audio buffer for this session
        self.session_audio_buffers[session_id] = []
    
    async def handle_disconnect(self, session_id: str) -> None:
        """
        Handle a client disconnection.
        
        Args:
            session_id: The session ID
        """
        logger.info(f"Client disconnected: {session_id}")
        
        # Clean up resources for this session
        if session_id in self.session_audio_buffers:
            del self.session_audio_buffers[session_id]
        
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
    
    async def process_audio_buffer(self, session_id: str, wake_word: Optional[str] = None) -> None:
        """
        Process the audio buffer for a session.
        
        Args:
            session_id: The session ID
            wake_word: Optional wake word that was detected
        """
        if session_id not in self.session_audio_buffers or not self.session_audio_buffers[session_id]:
            logger.warning(f"No audio buffer for session {session_id}")
            return
        
        # Get the session
        session = self.ws_server.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found")
            return
        
        # Get the audio buffer
        audio_buffer = self.session_audio_buffers[session_id]
        self.session_audio_buffers[session_id] = []  # Clear buffer
        
        # Process the audio through the agent graph - include audio format
        # information from the session
        audio_params = {
            "format": session.audio_format,
            "sample_rate": session.sample_rate,
            "channels": session.channels,
            "frame_duration": session.frame_duration
        }
        
        result = await self.agent_graph.process_audio_buffer(
            audio_buffer, session_id, audio_params, wake_word
        )
        
        # Send response to the client
        await self.send_agent_response(session_id, result)
    
    async def send_agent_response(self, session_id: str, result: Dict[str, Any]) -> None:
        """
        Send agent response to the client.
        
        Args:
            session_id: The session ID
            result: The agent result
        """
        # Send transcription if available
        if "transcription" in result and result["transcription"]:
            await self.ws_server.send_message(
                session_id,
                ProtocolMessage.create_stt_message(result["transcription"])
            )
        
        # Send IoT commands if available
        if "processed_iot_commands" in result and result["processed_iot_commands"]:
            await self.ws_server.send_message(
                session_id,
                ProtocolMessage.create_iot_command_message(result["processed_iot_commands"])
            )
        
        # Send emotion if available
        if "emotion" in result and result["emotion"]:
            await self.ws_server.send_message(
                session_id,
                ProtocolMessage.create_llm_emotion_message(
                    result["emotion"],
                    None  # Could add emoji based on emotion
                )
            )
        
        # Send function call if available
        if "function_call" in result and result["function_call"]:
            function_data = result["function_call"]
            await self.ws_server.send_message(
                session_id,
                ProtocolMessage.create_function_call_response_message(
                    function_data["name"],
                    function_data["arguments"]
                )
            )
        
        # For direct text input, send text response directly if TTS is skipped
        if result.get("skip_tts", False) and "response_text" in result and result["response_text"]:
            await self.ws_server.send_message(
                session_id,
                ProtocolMessage.create_text_response_message(result["response_text"])
            )
            
            # If client is in auto listening mode, send a listen start message
            session_info = self.active_sessions.get(session_id, {})
            keep_listening = result.get("keep_listening", False)
            if keep_listening and session_info.get("listen_mode") == ListenMode.AUTO:
                await self.ws_server.send_message(
                    session_id,
                    ProtocolMessage.create_listen_start_response(ListenMode.AUTO)
                )
            
            return
            
        # Send TTS response if available
        if "response_text" in result and result["response_text"]:
            response_text = result["response_text"]
            tts_data = result.get("tts_data", {})
            
            # Send TTS start message
            await self.ws_server.send_message(
                session_id,
                ProtocolMessage.create_tts_start_message()
            )
            
            # Generate speech frames
            voice = tts_data.get("voice", "alloy") if tts_data else "alloy"
            speed = tts_data.get("speed", 1.0) if tts_data else 1.0
            
            frames = await self.agent_graph.tts_node.generate_speech_frames(
                response_text, voice, speed
            )
            
            # Send each frame
            current_sentence = ""
            for sentence_text, audio_frame in frames:
                if sentence_text:
                    # New sentence, send the sentence text
                    current_sentence = sentence_text
                    await self.ws_server.send_message(
                        session_id,
                        ProtocolMessage.create_tts_sentence_message(sentence_text)
                    )
                
                if audio_frame:
                    # Send the audio frame
                    await self.ws_server.send_audio(session_id, audio_frame)
            
            # Send TTS stop message
            await self.ws_server.send_message(
                session_id,
                ProtocolMessage.create_tts_stop_message()
            )
            
            # If client is in auto listening mode and we should keep listening, 
            # send a listen start message
            session_info = self.active_sessions.get(session_id, {})
            keep_listening = result.get("keep_listening", False)
            if keep_listening and session_info.get("listen_mode") == ListenMode.AUTO:
                await self.ws_server.send_message(
                    session_id,
                    ProtocolMessage.create_listen_start_response(ListenMode.AUTO)
                )
    
    async def start(self) -> None:
        """Start the application."""
        logger.info("Starting application")
        self.setup_signal_handlers()
        await self.ws_server.start_server()
    
    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self.shutdown(s))
            )
    
    async def shutdown(self, sig: signal.Signals) -> None:
        """
        Shutdown the application gracefully.
        
        Args:
            sig: The signal that triggered the shutdown
        """
        logger.info(f"Received exit signal {sig.name}")
        
        # Close all WebSocket connections
        await self.ws_server.shutdown()
        
        # Additional cleanup as needed
        # ...
        
        logger.info("Application shutdown complete")
        
        # Stop the event loop
        asyncio.get_event_loop().stop()


async def main() -> None:
    """Application entry point."""
    app = Application()
    await app.start()


if __name__ == "__main__":
    asyncio.run(main()) 