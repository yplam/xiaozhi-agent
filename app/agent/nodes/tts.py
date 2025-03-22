"""
TTS (Text-to-Speech) node for LangGraph.
"""
from typing import Any, Dict, List, Optional, Tuple

from app.services.tts_service import TTSService
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class TTSNode:
    """
    LangGraph node for handling text-to-speech conversion.
    
    This node is responsible for converting text to speech
    using the TTS service.
    """
    
    def __init__(self):
        """Initialize the TTS node."""
        self.tts_service = TTSService()
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the state by converting text to speech if present.
        
        Args:
            state: The current state of the conversation
                Expected keys:
                - response_text: The text to convert to speech
                - voice: The voice to use (optional)
                - speed: The speech speed (optional)
                - skip_tts: Skip TTS processing (optional)
                
        Returns:
            Updated state with speech data
                Added keys:
                - tts_data: Dictionary containing audio data and metadata
                - tts_stream: Flag indicating whether to stream the audio
        """
        logger.info("Processing in TTS node")
        
        # Check if we should skip TTS
        if state.get("skip_tts", False):
            logger.info("Skipping TTS as requested")
            return state
            
        # Check if there's text to synthesize
        response_text = state.get("response_text", "")
        
        if not response_text:
            logger.warning("No text to synthesize")
            state["tts_data"] = None
            return state
        
        # Get parameters
        voice = state.get("voice", "alloy")
        speed = state.get("speed", 1.0)
        
        # Prepare for streaming
        state["tts_stream"] = True
        state["tts_data"] = {
            "text": response_text,
            "voice": voice,
            "speed": speed,
            "audio_frames": []  # Will be populated by the streaming function
        }
        
        # The actual streaming will be handled by the agent controller
        # when it detects the tts_stream flag is set
        
        return state
    
    async def generate_speech_frames(self, text: str, voice: str = "alloy", speed: float = 1.0) -> List[Tuple[str, Optional[bytes]]]:
        """
        Generate speech frames from text for streaming.
        
        Args:
            text: The text to synthesize
            voice: The voice to use
            speed: The speech speed
            
        Returns:
            List of (sentence_text, audio_frame) tuples
        """
        frames = []
        async for sentence_text, audio_frame in self.tts_service.stream_speech(
            text, voice, speed=speed
        ):
            frames.append((sentence_text, audio_frame))
        return frames
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the process method.
        
        Args:
            state: The current state
            
        Returns:
            Updated state
        """
        return await self.process(state) 