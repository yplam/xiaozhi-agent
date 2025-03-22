"""
WebSocket server implementation for client communication.
"""
import asyncio
import json
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Union, Awaitable

import websockets
from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServerProtocol

from app.config import (AUTH_ENABLED, AUTH_SECRET_KEY, DEFAULT_TIMEOUT,
                        WS_PROTOCOL_VERSION)
from app.server.protocol import (ListenMode, MessageType, ProtocolMessage,
                                 ProtocolParser)
from app.utils.audio import OpusCodec
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class ClientSession:
    """Represents a connected client session."""

    def __init__(self, websocket: WebSocketServerProtocol, client_id: str, device_id: str):
        """
        Initialize a client session.

        Args:
            websocket: The WebSocket connection
            client_id: The client identifier
            device_id: The device identifier
        """
        self.id = str(uuid.uuid4())
        self.websocket = websocket
        self.client_id = client_id
        self.device_id = device_id
        self.listening = False
        self.listen_mode: Optional[str] = None
        self.audio_buffer: List[bytes] = []
        self.connected_at = asyncio.get_event_loop().time()
        self.last_activity_at = self.connected_at
        self.opus_codec = OpusCodec()
        
        logger.info(f"Session created: {self.id} for client: {client_id}, device: {device_id}")
    
    async def send_message(self, message: Dict[str, Any]) -> None:
        """
        Send a message to the client.

        Args:
            message: The message to send
        """
        await self.websocket.send(json.dumps(message))
        self.last_activity_at = asyncio.get_event_loop().time()
    
    async def send_audio(self, audio_data: bytes) -> None:
        """
        Send audio data to the client.

        Args:
            audio_data: The audio data to send
        """
        await self.websocket.send(audio_data)
        self.last_activity_at = asyncio.get_event_loop().time()
    
    async def close(self) -> None:
        """Close the WebSocket connection."""
        await self.websocket.close()
        logger.info(f"Session closed: {self.id}")


class WebSocketServer:
    """WebSocket server for handling client connections."""

    def __init__(self, host: str, port: int):
        """
        Initialize the WebSocket server.

        Args:
            host: The host to bind to
            port: The port to bind to
        """
        self.host = host
        self.port = port
        self.sessions: Dict[str, ClientSession] = {}
        self.connected_clients: Set[str] = set()
        
        # Callback functions
        self.on_audio_handler: Optional[Callable[[str, bytes], Union[None, Awaitable[None]]]] = None
        self.on_message_handler: Optional[Callable[[str, Dict[str, Any]], Union[None, Awaitable[None]]]] = None
        self.on_connect_handler: Optional[Callable[[str, str, str], Union[None, Awaitable[None]]]] = None
        self.on_disconnect_handler: Optional[Callable[[str], Union[None, Awaitable[None]]]] = None
        
        logger.info(f"WebSocket server initialized on {host}:{port}")
    
    def register_audio_handler(self, handler: Callable[[str, bytes], Union[None, Awaitable[None]]]) -> None:
        """
        Register a callback for handling audio data.

        Args:
            handler: Callback function that takes session_id and audio_data
        """
        self.on_audio_handler = handler
    
    def register_message_handler(self, handler: Callable[[str, Dict[str, Any]], Union[None, Awaitable[None]]]) -> None:
        """
        Register a callback for handling JSON messages.

        Args:
            handler: Callback function that takes session_id and message
        """
        self.on_message_handler = handler
    
    def register_connect_handler(self, handler: Callable[[str, str, str], Union[None, Awaitable[None]]]) -> None:
        """
        Register a callback for client connections.

        Args:
            handler: Callback function that takes session_id, client_id, and device_id
        """
        self.on_connect_handler = handler
    
    def register_disconnect_handler(self, handler: Callable[[str], Union[None, Awaitable[None]]]) -> None:
        """
        Register a callback for client disconnections.

        Args:
            handler: Callback function that takes session_id
        """
        self.on_disconnect_handler = handler
    
    def get_session(self, session_id: str) -> Optional[ClientSession]:
        """
        Get a client session by ID.

        Args:
            session_id: The session ID

        Returns:
            The client session, or None if not found
        """
        return self.sessions.get(session_id)
    
    async def send_message(self, session_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to a client.

        Args:
            session_id: The session ID
            message: The message to send

        Returns:
            True if the message was sent, False otherwise
        """
        session = self.get_session(session_id)
        if session:
            try:
                await session.send_message(message)
                return True
            except ConnectionClosed:
                logger.warning(f"Connection closed when sending message to {session_id}")
                await self._handle_disconnect(session)
        return False
    
    async def send_audio(self, session_id: str, audio_data: bytes) -> bool:
        """
        Send audio data to a client.

        Args:
            session_id: The session ID
            audio_data: The audio data to send

        Returns:
            True if the audio data was sent, False otherwise
        """
        session = self.get_session(session_id)
        if session:
            try:
                await session.send_audio(audio_data)
                return True
            except ConnectionClosed:
                logger.warning(f"Connection closed when sending audio to {session_id}")
                await self._handle_disconnect(session)
        return False
    
    async def close_session(self, session_id: str) -> bool:
        """
        Close a client session.

        Args:
            session_id: The session ID

        Returns:
            True if the session was closed, False otherwise
        """
        session = self.get_session(session_id)
        if session:
            await session.close()
            await self._handle_disconnect(session)
            return True
        return False
    
    async def start_server(self) -> None:
        """Start the WebSocket server."""
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
        
        async def handler(websocket: WebSocketServerProtocol):
            await self._handle_connection(websocket)
        
        async with websockets.serve(handler, self.host, self.port):
            await asyncio.Future()  # Run forever
    
    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """
        Handle a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
        """
        # Get client information from headers
        headers = websocket.request.headers
        
        # Validate protocol version
        protocol_version = headers.get("Protocol-Version")
        if protocol_version is None:
            logger.warning(f"Missing protocol version header, continuing anyway")
        elif protocol_version != str(WS_PROTOCOL_VERSION):
            logger.warning(f"Invalid protocol version: {protocol_version}")
            await websocket.close(1002, "Invalid protocol version")
            return
        
        # Validate authentication if enabled
        if AUTH_ENABLED:
            auth_header = headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                logger.warning("Missing or invalid Authorization header")
                await websocket.close(1008, "Unauthorized")
                return
            
            token = auth_header[7:]  # Remove "Bearer " prefix
            if not self._validate_token(token):
                logger.warning("Invalid token")
                await websocket.close(1008, "Unauthorized")
                return
        
        # Get client and device IDs
        client_id = headers.get("Client-Id", "unknown")
        device_id = headers.get("Device-Id", "unknown")
        
        # Create client session
        session = ClientSession(websocket, client_id, device_id)
        self.sessions[session.id] = session
        
        try:
            # Wait for hello message
            hello_received = await self._wait_for_hello(session)
            if not hello_received:
                await session.close()
                del self.sessions[session.id]
                return
            
            # Send hello response
            await session.send_message(ProtocolMessage.create_hello_message())
            
            # Notify of new connection
            if self.on_connect_handler:
                await self.on_connect_handler(session.id, client_id, device_id)
            
            # Handle messages
            await self._handle_messages(session)
        except ConnectionClosed:
            logger.info(f"Connection closed for session {session.id}")
        except Exception as e:
            logger.exception(f"Error handling connection: {e}")
        finally:
            await self._handle_disconnect(session)
    
    async def _wait_for_hello(self, session: ClientSession) -> bool:
        """
        Wait for a hello message from the client.

        Args:
            session: The client session

        Returns:
            True if a valid hello message was received, False otherwise
        """
        try:
            data = await asyncio.wait_for(session.websocket.recv(), DEFAULT_TIMEOUT)
            
            try:
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                
                message = json.loads(data)
                
                if not ProtocolParser.is_hello_message(message):
                    logger.warning(f"Invalid hello message: {message}")
                    return False
                
                logger.info(f"Received hello message from {session.id}")
                return True
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in hello message")
                return False
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for hello message from {session.id}")
            return False
    
    async def _handle_messages(self, session: ClientSession) -> None:
        """
        Handle messages from a client.

        Args:
            session: The client session
        """
        async for data in session.websocket:
            if isinstance(data, bytes):
                # Binary data (audio)
                if session.listening and self.on_audio_handler:
                    await self.on_audio_handler(session.id, data)
            else:
                # Text data (JSON)
                try:
                    message = ProtocolParser.parse_message(data)
                    
                    if ProtocolParser.is_listen_start_message(message):
                        session.listening = True
                        session.listen_mode = message.get("mode")
                        logger.info(f"Client {session.id} started listening in mode: {session.listen_mode}")
                    
                    elif ProtocolParser.is_listen_stop_message(message):
                        session.listening = False
                        logger.info(f"Client {session.id} stopped listening")
                    
                    if self.on_message_handler:
                        await self.on_message_handler(session.id, message)
                except ValueError as e:
                    logger.warning(f"Invalid message from {session.id}: {e}")
    
    async def _handle_disconnect(self, session: ClientSession) -> None:
        """
        Handle a client disconnection.

        Args:
            session: The client session
        """
        if session.id in self.sessions:
            del self.sessions[session.id]
            
            if self.on_disconnect_handler:
                await self.on_disconnect_handler(session.id)
            
            logger.info(f"Client disconnected: {session.id}")
    
    def _validate_token(self, token: str) -> bool:
        """
        Validate an authentication token.

        Args:
            token: The token to validate

        Returns:
            True if the token is valid, False otherwise
        """
        # This is a simple validation. In a real app, you might want to use JWT
        # or another token validation method.
        return token == AUTH_SECRET_KEY 