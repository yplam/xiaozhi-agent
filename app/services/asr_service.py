"""
ASR (Automatic Speech Recognition) service implementation.
"""
import asyncio
from typing import Callable, List, Optional

import httpx
import openai
from httpx import AsyncClient

from app.config import OPENAI_API_KEY, PROXY_URL, PROXY_ENABLED
from app.utils.audio import OpusCodec
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class ASRService:
    """
    Service for converting speech to text using OpenAI's API.
    """

    def __init__(self):
        """Initialize the ASR service."""
        self.opus_codec = OpusCodec()
        self.openai_client = self._create_openai_client()
        logger.info("ASR service initialized")

    def _create_openai_client(self) -> openai.AsyncOpenAI:
        """
        Create an OpenAI client with proxy if configured.

        Returns:
            AsyncOpenAI client
        """
        http_client = None
        
        if PROXY_ENABLED and PROXY_URL:
            http_client = AsyncClient(proxy=PROXY_URL)
            logger.info(f"Using HTTP proxy: {PROXY_URL}")
        
        return openai.AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            http_client=http_client,
        )

    async def transcribe_audio_buffer(self, audio_buffer: List[bytes]) -> str:
        """
        Transcribe audio buffer to text using OpenAI API.

        Args:
            audio_buffer: List of Opus-encoded audio frames

        Returns:
            Transcribed text
        """
        if not audio_buffer:
            return ""
        
        # Decode Opus frames and concatenate
        pcm_chunks = []
        for opus_frame in audio_buffer:
            try:
                pcm_chunk = self.opus_codec.decode(opus_frame)
                pcm_chunks.append(pcm_chunk)
            except Exception as e:
                logger.error(f"Error decoding Opus frame: {e}")
        
        if not pcm_chunks:
            return ""
        
        # Concatenate PCM chunks
        combined_pcm = b"".join(pcm_chunks)
        
        # Transcribe using OpenAI
        try:
            response = await self._transcribe_with_openai(combined_pcm)
            return response
        except Exception as e:
            logger.error(f"Error transcribing with OpenAI: {e}")
            return ""

    async def _transcribe_with_openai(self, audio_data: bytes) -> str:
        """
        Transcribe audio data using OpenAI Whisper API.

        Args:
            audio_data: PCM audio data

        Returns:
            Transcribed text
        """
        import tempfile
        
        # Create a temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_file:
            # Write WAV header
            # Simple WAV header for 16-bit PCM, 16000 Hz, 1 channel
            wav_header = bytes([
                # RIFF header
                0x52, 0x49, 0x46, 0x46,  # "RIFF"
                0x00, 0x00, 0x00, 0x00,  # Size (to be filled)
                0x57, 0x41, 0x56, 0x45,  # "WAVE"
                
                # fmt chunk
                0x66, 0x6d, 0x74, 0x20,  # "fmt "
                0x10, 0x00, 0x00, 0x00,  # Chunk size: 16
                0x01, 0x00,              # Format: 1 (PCM)
                0x01, 0x00,              # Channels: 1
                0x80, 0x3e, 0x00, 0x00,  # Sample rate: 16000
                0x00, 0x7d, 0x00, 0x00,  # Byte rate: 16000*2
                0x02, 0x00,              # Block align: 2
                0x10, 0x00,              # Bits per sample: 16
                
                # data chunk
                0x64, 0x61, 0x74, 0x61,  # "data"
                0x00, 0x00, 0x00, 0x00,  # Size (to be filled)
            ])
            
            # Fill size fields
            data_size = len(audio_data)
            file_size = data_size + 36  # 36 is the size of the header minus 8
            
            # Update RIFF chunk size (file size - 8)
            wav_header = bytearray(wav_header)
            wav_header[4:8] = (file_size - 8).to_bytes(4, byteorder="little")
            
            # Update data chunk size
            wav_header[40:44] = data_size.to_bytes(4, byteorder="little")
            
            # Write header and audio data
            temp_file.write(wav_header)
            temp_file.write(audio_data)
            temp_file.flush()
            
            # Call Whisper API
            with open(temp_file.name, "rb") as audio_file:
                response = await self.openai_client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-1",
                    language="en",  # Can be parameterized
                )
            
            return response.text

    async def process_realtime_audio(
        self, 
        audio_frames: asyncio.Queue, 
        callback: Callable[[str], None],
        max_batch_frames: int = 50,
        silence_threshold: int = 100  # ms
    ) -> None:
        """
        Process audio frames in real-time and call the callback with transcriptions.
        
        Args:
            audio_frames: Queue of audio frames
            callback: Function to call with transcribed text
            max_batch_frames: Maximum number of frames to batch before processing
            silence_threshold: Time in ms to wait for more audio before processing
        """
        buffer = []
        last_frame_time = None
        
        while True:
            try:
                # Get next frame with timeout
                try:
                    frame = await asyncio.wait_for(audio_frames.get(), silence_threshold / 1000)
                    buffer.append(frame)
                    last_frame_time = asyncio.get_event_loop().time()
                    
                    # If we have enough frames, process them
                    if len(buffer) >= max_batch_frames:
                        text = await self.transcribe_audio_buffer(buffer)
                        if text:
                            callback(text)
                        buffer = []
                except asyncio.TimeoutError:
                    # No new frames for a while, process what we have
                    if buffer:
                        text = await self.transcribe_audio_buffer(buffer)
                        if text:
                            callback(text)
                        buffer = []
            except Exception as e:
                logger.error(f"Error in real-time audio processing: {e}")
                buffer = [] 