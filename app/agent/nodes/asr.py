"""
ASR (Automatic Speech Recognition) node for LangGraph.
"""
from typing import Any, Dict, List, Tuple

from app.services.asr_service import ASRService
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class ASRNode:
    """
    LangGraph node for handling speech recognition.
    
    This node is responsible for processing audio data and converting it to text
    using the ASR service.
    """
    
    def __init__(self):
        """Initialize the ASR node."""
        self.asr_service = ASRService()
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the state by transcribing audio data if present.
        
        Args:
            state: The current state of the conversation
                Expected keys:
                - audio_buffer: List of audio frames to transcribe (optional)
                - transcription: Pre-existing transcription (optional)
                
        Returns:
            Updated state with transcription results
                Added keys:
                - transcription: The transcribed text
        """
        logger.info("Processing in ASR node")
        
        # If there's already transcription in the state, pass it through
        if "transcription" in state and state["transcription"]:
            logger.info(f"Using existing transcription: {state['transcription']}")
            state["has_new_user_input"] = True
            return state
        
        # Check if there's audio data to process
        audio_buffer = state.get("audio_buffer", [])
        
        if not audio_buffer:
            logger.warning("No audio data to transcribe")
            state["transcription"] = ""
            return state
        
        # Transcribe audio
        try:
            transcription = await self.asr_service.transcribe_audio_buffer(audio_buffer)
            logger.info(f"Transcription: {transcription}")
            
            # Update state
            state["transcription"] = transcription
            
            # Clear audio buffer after processing
            state["audio_buffer"] = []
            
            # Set a flag to indicate new user input
            state["has_new_user_input"] = bool(transcription)
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            state["transcription"] = ""
            state["error"] = str(e)
        
        return state
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the process method.
        
        Args:
            state: The current state
            
        Returns:
            Updated state
        """
        return await self.process(state) 