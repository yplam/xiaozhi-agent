"""
Audio utilities for handling Opus audio encoding/decoding.
"""
import io
from typing import Dict, Optional, Tuple, Union

import numpy as np
from opuslib import Decoder, Encoder
from app.config import CHANNELS, OPUS_FRAME_DURATION_MS, SAMPLE_RATE
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class OpusCodec:
    """
    Handles Opus encoding and decoding for audio data.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        frame_duration_ms: int = OPUS_FRAME_DURATION_MS,
    ):
        """
        Initialize the Opus codec.

        Args:
            sample_rate: Sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1)
            frame_duration_ms: Frame duration in milliseconds (default: 60)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_duration_ms = frame_duration_ms
        
        # Calculate frame size based on sample rate and frame duration
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        
        # Initialize encoder and decoder
        # opuslib uses application types: AUDIO(2048), VOIP(2048), RESTRICTED_LOWDELAY(2051)
        self.encoder = Encoder(self.sample_rate, self.channels, 2048)  # AUDIO application type
        self.decoder = Decoder(self.sample_rate, self.channels)
        
        logger.info(
            f"Initialized OpusCodec: sample_rate={sample_rate}, "
            f"channels={channels}, frame_duration_ms={frame_duration_ms}"
        )

    def encode(self, pcm_data: Union[bytes, np.ndarray]) -> bytes:
        """
        Encode PCM data to Opus format.

        Args:
            pcm_data: PCM audio data as bytes or numpy array

        Returns:
            Opus encoded bytes
        """
        if isinstance(pcm_data, np.ndarray):
            # Convert numpy array to bytes
            pcm_data = pcm_data.tobytes()
        
        return self.encoder.encode(pcm_data, self.frame_size)

    def decode(self, opus_data: bytes) -> bytes:
        """
        Decode Opus data to PCM format.

        Args:
            opus_data: Opus encoded audio data

        Returns:
            PCM audio data as bytes
        """
        return self.decoder.decode(opus_data, self.frame_size)

    def pcm_to_numpy(self, pcm_data: bytes) -> np.ndarray:
        """
        Convert PCM bytes to numpy array.

        Args:
            pcm_data: PCM audio data as bytes

        Returns:
            Numpy array of audio samples
        """
        return np.frombuffer(pcm_data, dtype=np.int16)

    def numpy_to_pcm(self, numpy_data: np.ndarray) -> bytes:
        """
        Convert numpy array to PCM bytes.

        Args:
            numpy_data: Numpy array of audio samples

        Returns:
            PCM audio data as bytes
        """
        return numpy_data.astype(np.int16).tobytes()


def get_audio_params() -> Dict[str, Union[str, int]]:
    """
    Get the audio parameters for the hello message.

    Returns:
        Dictionary of audio parameters
    """
    return {
        "format": "opus",
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "frame_duration": OPUS_FRAME_DURATION_MS,
    } 