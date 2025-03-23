"""
WebSocket protocol implementation based on the documented protocol.
"""
import json
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from app.config import WS_PROTOCOL_VERSION
from app.utils.audio import get_audio_params
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class MessageType(str, Enum):
    """Message types used in the protocol."""
    HELLO = "hello"
    LISTEN = "listen"
    STT = "stt"
    TTS = "tts"
    ABORT = "abort"
    IOT = "iot"
    LLM = "llm"
    TEXT_RESPONSE = "text_response"
    FUNCTION_CALL = "function_call"  # Added for compatibility with xiaozhi-server


class ListenState(str, Enum):
    """States for the listen message type."""
    START = "start"
    STOP = "stop"
    DETECT = "detect"


class ListenMode(str, Enum):
    """Modes for the listen message type."""
    AUTO = "auto"
    MANUAL = "manual"
    REALTIME = "realtime"


class TTSState(str, Enum):
    """States for the TTS message type."""
    START = "start"
    STOP = "stop"
    SENTENCE_START = "sentence_start"


class AbortReason(str, Enum):
    """Reasons for abort messages."""
    NONE = "none"
    USER_REQUESTED = "user_requested"
    WAKE_WORD_DETECTED = "wake_word_detected"
    TIMEOUT = "timeout"


class ProtocolMessage:
    """Base class for all protocol messages."""
    
    @staticmethod
    def create_hello_message() -> Dict[str, Any]:
        """
        Create a hello message to be sent from the server to the client.
        
        Returns:
            A hello message dictionary
        """
        return {
            "type": MessageType.HELLO,
            "transport": "websocket",
            "audio_params": {
                "format": "opus",
                "sample_rate": get_audio_params()["sample_rate"]
            },
            "protocol_version": WS_PROTOCOL_VERSION
        }
    
    @staticmethod
    def create_tts_start_message() -> Dict[str, Any]:
        """
        Create a TTS start message.
        
        Returns:
            A TTS start message dictionary
        """
        return {
            "type": MessageType.TTS,
            "state": TTSState.START
        }
    
    @staticmethod
    def create_tts_stop_message() -> Dict[str, Any]:
        """
        Create a TTS stop message.
        
        Returns:
            A TTS stop message dictionary
        """
        return {
            "type": MessageType.TTS,
            "state": TTSState.STOP
        }
    
    @staticmethod
    def create_tts_sentence_message(text: str) -> Dict[str, Any]:
        """
        Create a TTS sentence start message with the text to be spoken.
        
        Args:
            text: The text to be spoken
            
        Returns:
            A TTS sentence start message dictionary
        """
        return {
            "type": MessageType.TTS,
            "state": TTSState.SENTENCE_START,
            "text": text
        }
    
    @staticmethod
    def create_stt_message(text: str) -> Dict[str, Any]:
        """
        Create an STT message with the recognized text.
        
        Args:
            text: The recognized text
            
        Returns:
            An STT message dictionary
        """
        return {
            "type": MessageType.STT,
            "text": text
        }
    
    @staticmethod
    def create_llm_emotion_message(emotion: str, text: Optional[str] = None) -> Dict[str, Any]:
        """
        Create an LLM emotion message.
        
        Args:
            emotion: The emotion type
            text: Optional emoji or text to display
            
        Returns:
            An LLM emotion message dictionary
        """
        message = {
            "type": MessageType.LLM,
            "emotion": emotion
        }
        
        if text:
            message["text"] = text
            
        return message
    
    @staticmethod
    def create_iot_command_message(commands: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create an IoT command message.
        
        Args:
            commands: List of IoT commands
            
        Returns:
            An IoT command message dictionary
        """
        return {
            "type": MessageType.IOT,
            "commands": commands
        }
    
    @staticmethod
    def create_text_response_message(text: str) -> Dict[str, Any]:
        """
        Create a text response message for direct text communication.
        
        Args:
            text: The text response
            
        Returns:
            A text response message dictionary
        """
        return {
            "type": MessageType.TEXT_RESPONSE,
            "text": text
        }
    
    @staticmethod
    def create_function_call_response_message(function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a function call response message.
        
        Args:
            function_name: The name of the function to call
            arguments: The function arguments
            
        Returns:
            A function call message dictionary
        """
        return {
            "type": MessageType.FUNCTION_CALL,
            "function": function_name,
            "arguments": arguments
        }
    
    @staticmethod
    def create_listen_start_response(mode: str = ListenMode.AUTO) -> Dict[str, Any]:
        """
        Create a listen start response message.
        
        Args:
            mode: The listening mode
            
        Returns:
            A listen start response message dictionary
        """
        return {
            "type": MessageType.LISTEN,
            "state": ListenState.START,
            "mode": mode
        }
    
    @staticmethod
    def create_listen_stop_response() -> Dict[str, Any]:
        """
        Create a listen stop response message.
        
        Returns:
            A listen stop response message dictionary
        """
        return {
            "type": MessageType.LISTEN,
            "state": ListenState.STOP
        }
    
    @staticmethod
    def create_abort_response(reason: str = AbortReason.NONE) -> Dict[str, Any]:
        """
        Create an abort response message.
        
        Args:
            reason: The abort reason
            
        Returns:
            An abort response message dictionary
        """
        return {
            "type": MessageType.ABORT,
            "reason": reason
        }


class ProtocolParser:
    """Parser for WebSocket protocol messages."""
    
    @staticmethod
    def parse_message(data: Union[str, bytes]) -> Dict[str, Any]:
        """
        Parse a message from the client.
        
        Args:
            data: The message data as string or bytes
            
        Returns:
            Parsed message as a dictionary
            
        Raises:
            ValueError: If the message is invalid JSON or missing required fields
        """
        try:
            if isinstance(data, bytes):
                data = data.decode("utf-8")
                
            message = json.loads(data)
            
            if "type" not in message:
                raise ValueError("Missing message type")
                
            return message
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            raise ValueError(f"Invalid JSON: {e}")
    
    @staticmethod
    def is_hello_message(message: Dict[str, Any]) -> bool:
        """
        Check if a message is a hello message.
        
        Args:
            message: The message to check
            
        Returns:
            True if the message is a hello message, False otherwise
        """
        return (
            message.get("type") == MessageType.HELLO and
            "transport" in message and
            "audio_params" in message
        )
    
    @staticmethod
    def is_listen_start_message(message: Dict[str, Any]) -> bool:
        """
        Check if a message is a listen start message.
        
        Args:
            message: The message to check
            
        Returns:
            True if the message is a listen start message, False otherwise
        """
        return (
            message.get("type") == MessageType.LISTEN and
            message.get("state") == ListenState.START and
            "mode" in message
        )
    
    @staticmethod
    def is_listen_stop_message(message: Dict[str, Any]) -> bool:
        """
        Check if a message is a listen stop message.
        
        Args:
            message: The message to check
            
        Returns:
            True if the message is a listen stop message, False otherwise
        """
        return (
            message.get("type") == MessageType.LISTEN and
            message.get("state") == ListenState.STOP
        )
    
    @staticmethod
    def is_wake_word_message(message: Dict[str, Any]) -> bool:
        """
        Check if a message is a wake word detection message.
        
        Args:
            message: The message to check
            
        Returns:
            True if the message is a wake word detection message, False otherwise
        """
        return (
            message.get("type") == MessageType.LISTEN and
            message.get("state") == ListenState.DETECT and
            "text" in message
        )
    
    @staticmethod
    def is_abort_message(message: Dict[str, Any]) -> bool:
        """
        Check if a message is an abort message.
        
        Args:
            message: The message to check
            
        Returns:
            True if the message is an abort message, False otherwise
        """
        return message.get("type") == MessageType.ABORT
    
    @staticmethod
    def is_iot_message(message: Dict[str, Any]) -> bool:
        """
        Check if a message is an IoT message.
        
        Args:
            message: The message to check
            
        Returns:
            True if the message is an IoT message, False otherwise
        """
        return (
            message.get("type") == MessageType.IOT and
            ("descriptors" in message or "states" in message or "commands" in message)
        )
    
    @staticmethod
    def is_function_call_message(message: Dict[str, Any]) -> bool:
        """
        Check if a message is a function call message.
        
        Args:
            message: The message to check
            
        Returns:
            True if the message is a function call message, False otherwise
        """
        return (
            message.get("type") == MessageType.FUNCTION_CALL and
            "function" in message and
            "arguments" in message
        ) 