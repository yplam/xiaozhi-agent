"""
TTS (Text-to-Speech) service implementation.
"""
import asyncio
import io
import re
from typing import AsyncGenerator, Dict, List, Optional, Tuple, Union

import httpx
import numpy as np
import openai
from httpx import AsyncClient

from app.config import OPENAI_API_KEY, PROXY_URL, PROXY_ENABLED
from app.utils.audio import OpusCodec
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class TTSService:
    """
    Service for converting text to speech using OpenAI's API.
    """

    def __init__(self):
        """Initialize the TTS service."""
        self.opus_codec = OpusCodec()
        self.openai_client = self._create_openai_client()
        logger.info("TTS service initialized")

    def _create_openai_client(self) -> openai.AsyncOpenAI:
        """
        Create an OpenAI client with proxy if configured.

        Returns:
            AsyncOpenAI client
        """
        http_client = None
        
        if PROXY_ENABLED and PROXY_URL:
            # Updated proxy configuration for newer httpx versions
            proxies = {"http://": PROXY_URL, "https://": PROXY_URL}
            http_client = AsyncClient(proxies=proxies)
            logger.info(f"Using HTTP proxy: {PROXY_URL}")
        
        return openai.AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            http_client=http_client,
        )

    def _split_text_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences for better TTS processing.

        Args:
            text: The text to split

        Returns:
            List of sentences
        """
        # Split on common sentence terminators, preserving the terminator
        sentences = re.findall(r'[^.!?]+[.!?]?', text)
        return [s.strip() for s in sentences if s.strip()]

    async def synthesize_speech(
        self, 
        text: str, 
        voice: str = "alloy",
        model: str = "tts-1",
        speed: float = 1.0
    ) -> bytes:
        """
        Synthesize speech from text using OpenAI API.

        Args:
            text: The text to synthesize
            voice: The voice to use (e.g., alloy, echo, fable, onyx, nova, shimmer)
            model: The TTS model to use
            speed: The speed of the speech (0.25-4.0)

        Returns:
            The raw audio data (MP3 format)
        """
        try:
            response = await self.openai_client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                speed=speed,
                response_format="mp3"
            )
            
            # Get the binary content from the response
            audio_data = await response.read()
            return audio_data
        except Exception as e:
            logger.error(f"Error synthesizing speech: {e}")
            raise

    async def mp3_to_opus_frames(self, mp3_data: bytes) -> List[bytes]:
        """
        Convert MP3 audio data to Opus frames.

        Args:
            mp3_data: The MP3 audio data

        Returns:
            List of Opus frames
        """
        try:
            import io
            import wave
            import tempfile
            from pydub import AudioSegment
            
            # Convert MP3 to WAV using pydub
            mp3_segment = AudioSegment.from_mp3(io.BytesIO(mp3_data))
            
            # Resample to our target sample rate
            mp3_segment = mp3_segment.set_frame_rate(self.opus_codec.sample_rate)
            
            # Convert to mono if needed
            if mp3_segment.channels > 1:
                mp3_segment = mp3_segment.set_channels(self.opus_codec.channels)
            
            # Convert to PCM
            wav_data = mp3_segment.raw_data
            
            # Encode to Opus frames
            opus_frames = []
            frame_size_bytes = self.opus_codec.frame_size * self.opus_codec.channels * 2  # 2 bytes per sample (16-bit)
            
            for i in range(0, len(wav_data), frame_size_bytes):
                frame = wav_data[i:i+frame_size_bytes]
                if len(frame) < frame_size_bytes:
                    # Pad the last frame if needed
                    frame = frame + b'\x00' * (frame_size_bytes - len(frame))
                
                opus_frame = self.opus_codec.encode(frame)
                opus_frames.append(opus_frame)
            
            return opus_frames
        except Exception as e:
            logger.error(f"Error converting MP3 to Opus: {e}")
            return []

    async def stream_speech(
        self, 
        text: str, 
        voice: str = "alloy",
        model: str = "tts-1",
        speed: float = 1.0,
        chunk_size: int = 4096  # Adjust based on latency requirements
    ) -> AsyncGenerator[Tuple[str, Optional[bytes]], None]:
        """
        Stream speech from text, yielding sentence text and audio chunks.
        
        This allows for real-time handling of TTS with sentence markers.

        Args:
            text: The text to synthesize
            voice: The voice to use
            model: The TTS model to use
            speed: The speed of the speech
            chunk_size: Size of audio chunks to yield

        Yields:
            Tuples of (sentence_text, audio_chunk)
            - First yield for each sentence is (sentence_text, None) as a marker
            - Subsequent yields are ("", audio_chunk) with the audio data
        """
        sentences = self._split_text_into_sentences(text)
        
        for sentence in sentences:
            # Yield the sentence text as a marker (for TTS_SENTENCE_START message)
            yield (sentence, None)
            
            try:
                # Synthesize this sentence
                mp3_data = await self.synthesize_speech(
                    sentence, voice, model, speed
                )
                
                # Convert to Opus frames
                opus_frames = await self.mp3_to_opus_frames(mp3_data)
                
                # Yield each Opus frame
                for frame in opus_frames:
                    yield ("", frame)
                    
                    # Optional delay to simulate real-time speech
                    await asyncio.sleep(0.01)
                    
            except Exception as e:
                logger.error(f"Error streaming sentence '{sentence}': {e}")
                continue 