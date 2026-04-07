"""
Bailian (Alibaba Cloud DashScope) Text-to-Speech implementation.

DashScope TTS API uses a different protocol from OpenAI, so we need
a custom implementation to support it.

API Documentation:
    POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
    Authorization: Bearer $DASHSCOPE_API_KEY
    Content-Type: application/json
    
    Request body:
    {
        "model": "qwen3-tts-flash",
        "input": {
            "text": "...",
            "voice": "Cherry",  # 默认使用 qwen3-tts 预置语音
            "language_type": "Chinese"
        }
    }
"""

import asyncio
import base64
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx
from loguru import logger

# Import esperanto types for compatibility
from esperanto.common_types.tts import AudioResponse, Voice


# Available voices for DashScope TTS (qwen3-tts series)
DASHSCOPE_TTS_VOICES = {
    # qwen3-tts 预置语音
    "Cherry": Voice(name="Cherry", id="Cherry", gender="FEMALE", language_code="zh-CN", description="Female Chinese voice"),
    "Serena": Voice(name="Serena", id="Serena", gender="FEMALE", language_code="zh-CN", description="Female Chinese voice"),
    "Ethan": Voice(name="Ethan", id="Ethan", gender="MALE", language_code="zh-CN", description="Male Chinese voice"),
    "Chelsie": Voice(name="Chelsie", id="Chelsie", gender="FEMALE", language_code="zh-CN", description="Female Chinese voice"),
}

# Default voice for testing
DEFAULT_DASHSCOPE_VOICE = "Cherry"


class DashScopeTextToSpeech:
    """
    DashScope (Qwen) Text-to-Speech model implementation.
    
    This class provides a compatible interface with Esperanto's TextToSpeechModel
    but uses DashScope's native TTS API protocol.
    """
    
    # Esperanto-compatible class attributes
    PROVIDER = "dashscope"
    DEFAULT_MODEL = "qwen3-tts-flash"
    DEFAULT_VOICE = DEFAULT_DASHSCOPE_VOICE
    COMMON_SSML_TAGS = []  # DashScope doesn't use SSML
    
    # DashScope TTS API endpoint
    API_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    
    def __init__(
        self,
        model_name: str = "qwen3-tts-flash",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        language_type: str = "Chinese",
        config: Optional[Dict[str, Any]] = None,
        timeout: float = 60.0,
        **kwargs: Any,
    ):
        """
        Initialize DashScope TTS model.
        
        Args:
            model_name: Model name (e.g., "qwen3-tts-flash")
            api_key: DashScope API key
            base_url: Not used, kept for esperanto compatibility
            language_type: Language type (e.g., "Chinese", "English")
            config: Configuration dict (Esperanto-compatible)
            timeout: Request timeout in seconds
            **kwargs: Additional configuration options
        """
        self.model_name = model_name
        # Support config dict (Esperanto-style) and env var fallback
        if config:
            self.api_key = api_key or config.get("api_key") or os.environ.get("DASHSCOPE_API_KEY")
        else:
            self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        self.language_type = language_type
        self.config = config or {}
        self._config = kwargs
        self.base_url = base_url
        self.timeout = timeout
        
        # Esperanto-compatible instance attributes
        self.provider = self.PROVIDER
        
    @property
    def available_voices(self) -> Dict[str, Voice]:
        """Return available voices for this model."""
        return DASHSCOPE_TTS_VOICES.copy()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def generate_speech(
        self,
        text: str,
        voice: str = DEFAULT_DASHSCOPE_VOICE,
        output_file: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ) -> AudioResponse:
        """
        Generate speech from text using DashScope TTS API (synchronous).
        
        Args:
            text: Text to convert to speech
            voice: Voice name (e.g., "Cherry", "Ethan")
            output_file: Optional path to save the audio file
            **kwargs: Additional options (e.g., language_type)
            
        Returns:
            AudioResponse containing the audio data
            
        Raises:
            ValueError: If API key is not configured
            RuntimeError: If API call fails
        """
        if not self.api_key:
            raise ValueError("DashScope API key not configured")
        
        # Prepare request payload
        payload = {
            "model": self.model_name,
            "input": {
                "text": text,
                "voice": voice,
                "language_type": kwargs.get("language_type", self.language_type),
            }
        }
        
        logger.debug(f"DashScope TTS request: model={self.model_name}, voice={voice}")
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.API_ENDPOINT,
                    json=payload,
                    headers=self._get_headers(),
                )
                
                if response.status_code == 429:
                    # Rate limit - wait and retry
                    logger.warning("DashScope TTS rate limit hit, waiting 2 seconds...")
                    import time
                    time.sleep(2)
                    response = client.post(
                        self.API_ENDPOINT,
                        json=payload,
                        headers=self._get_headers(),
                    )
                
                if response.status_code != 200:
                    error_msg = response.text[:500] if response.text else "Unknown error"
                    logger.error(f"DashScope TTS API error: {response.status_code} - {error_msg}")
                    raise RuntimeError(f"DashScope TTS API error: {response.status_code} - {error_msg}")
                
                return self._parse_response(response, text, voice, output_file, client)
                
        except httpx.TimeoutException:
            raise RuntimeError("DashScope TTS request timed out")
        except httpx.RequestError as e:
            raise RuntimeError(f"DashScope TTS request failed: {str(e)}")
    
    async def agenerate_speech(
        self,
        text: str,
        voice: str = DEFAULT_DASHSCOPE_VOICE,
        output_file: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ) -> AudioResponse:
        """
        Generate speech from text using DashScope TTS API (async).
        
        Args:
            text: Text to convert to speech
            voice: Voice name (e.g., "Cherry", "Ethan")
            output_file: Optional path to save the audio file
            **kwargs: Additional options (e.g., language_type)
            
        Returns:
            AudioResponse containing the audio data
            
        Raises:
            ValueError: If API key is not configured
            RuntimeError: If API call fails
        """
        if not self.api_key:
            raise ValueError("DashScope API key not configured")
        
        # Prepare request payload
        payload = {
            "model": self.model_name,
            "input": {
                "text": text,
                "voice": voice,
                "language_type": kwargs.get("language_type", self.language_type),
            }
        }
        
        logger.debug(f"DashScope TTS request: model={self.model_name}, voice={voice}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.API_ENDPOINT,
                    json=payload,
                    headers=self._get_headers(),
                )
                
                if response.status_code == 429:
                    # Rate limit - wait and retry
                    logger.warning("DashScope TTS rate limit hit, waiting 2 seconds...")
                    await asyncio.sleep(2)
                    response = await client.post(
                        self.API_ENDPOINT,
                        json=payload,
                        headers=self._get_headers(),
                    )
                
                if response.status_code != 200:
                    error_msg = response.text[:500] if response.text else "Unknown error"
                    logger.error(f"DashScope TTS API error: {response.status_code} - {error_msg}")
                    raise RuntimeError(f"DashScope TTS API error: {response.status_code} - {error_msg}")
                
                return self._parse_response(response, text, voice, output_file, client)
                
        except httpx.TimeoutException:
            raise RuntimeError("DashScope TTS request timed out")
        except httpx.RequestError as e:
            raise RuntimeError(f"DashScope TTS request failed: {str(e)}")
    
    def _parse_response(
        self,
        response: httpx.Response,
        text: str,
        voice: str,
        output_file: Optional[Union[str, Path]],
        client: Union[httpx.Client, httpx.AsyncClient],
    ) -> AudioResponse:
        """Parse DashScope TTS response and return AudioResponse."""
        data = response.json()
        logger.debug(f"DashScope TTS raw response: {data}")
        
        # Parse response - DashScope TTS returns audio info in output.audio
        output = data.get("output", {})
        audio_info = output.get("audio", {})
        
        # Handle different response formats
        audio_url = None
        audio_base64 = None
        
        if isinstance(audio_info, dict):
            # New format: audio is a dict with url and optional data
            audio_url = audio_info.get("url")
            audio_base64 = audio_info.get("data") if audio_info.get("data") else None
        elif isinstance(audio_info, str):
            # Old format: audio is base64 string directly
            audio_base64 = audio_info
        
        # Get audio content
        audio_content = None
        
        if audio_url:
            # Download audio from URL
            logger.debug(f"Downloading audio from URL: {audio_url}")
            if isinstance(client, httpx.AsyncClient):
                # For async client, we need to handle this differently
                # This shouldn't happen in the sync path
                raise RuntimeError("Async client used in sync context")
            else:
                audio_response = client.get(audio_url)
                if audio_response.status_code == 200:
                    audio_content = audio_response.content
                else:
                    raise RuntimeError(f"Failed to download audio: {audio_response.status_code}")
        elif audio_base64:
            # Decode base64 audio
            audio_content = base64.b64decode(audio_base64)
        
        if not audio_content:
            logger.error(f"DashScope TTS response missing audio data: {data}")
            raise RuntimeError(f"DashScope TTS response missing audio data. Response: {str(data)[:500]}")
        
        logger.debug(f"DashScope TTS generated {len(audio_content)} bytes of audio")
        
        # Determine audio format
        audio_format = "wav"
        content_type = "audio/wav"
        if audio_url and ".mp3" in audio_url:
            audio_format = "mp3"
            content_type = "audio/mpeg"
        elif audio_info and isinstance(audio_info, dict):
            fmt = audio_info.get("format", audio_format)
            if fmt == "mp3":
                audio_format = "mp3"
                content_type = "audio/mpeg"
        
        # Save to file if specified
        if output_file:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_bytes(audio_content)
        
        return AudioResponse(
            audio_data=audio_content,
            content_type=content_type,
            model=self.model_name,
            voice=voice,
            provider=self.provider,
            metadata={"text": text}
        )
    
    def _get_models(self) -> List:
        """Return available models (for compatibility)."""
        return []


# Keep old name for backward compatibility
BailianTextToSpeech = DashScopeTextToSpeech
BAILIAN_VOICES = DASHSCOPE_TTS_VOICES
DEFAULT_BAILIAN_VOICE = DEFAULT_DASHSCOPE_VOICE


def create_bailian_tts(
    model_name: str,
    config: Optional[Dict[str, Any]] = None,
) -> DashScopeTextToSpeech:
    """
    Factory function to create DashScope TTS model.
    
    Args:
        model_name: Model name (e.g., "qwen3-tts-flash")
        config: Configuration dict containing api_key and other options
        
    Returns:
        DashScopeTextToSpeech instance
    """
    config = config or {}
    
    return DashScopeTextToSpeech(
        model_name=model_name,
        api_key=config.get("api_key"),
        language_type=config.get("language_type", "Chinese"),
        **{k: v for k, v in config.items() if k not in ("api_key", "language_type")},
    )
