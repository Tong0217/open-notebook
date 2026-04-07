"""
DashScope (Alibaba Cloud) Text-to-Speech implementation.

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
            "voice": "Cherry",
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
    "Cherry": Voice(name="Cherry", id="Cherry", gender="FEMALE", language_code="zh-CN", description="Female Chinese voice"),
    "Serena": Voice(name="Serena", id="Serena", gender="FEMALE", language_code="zh-CN", description="Female Chinese voice"),
    "Ethan": Voice(name="Ethan", id="Ethan", gender="MALE", language_code="zh-CN", description="Male Chinese voice"),
    "Chelsie": Voice(name="Chelsie", id="Chelsie", gender="FEMALE", language_code="zh-CN", description="Female Chinese voice"),
}

DEFAULT_DASHSCOPE_VOICE = "Cherry"


class DashScopeTextToSpeech:
    """DashScope (Qwen) Text-to-Speech model implementation."""
    
    PROVIDER = "dashscope"
    DEFAULT_MODEL = "qwen3-tts-flash"
    DEFAULT_VOICE = DEFAULT_DASHSCOPE_VOICE
    COMMON_SSML_TAGS = []
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
        self.model_name = model_name
        if config:
            self.api_key = api_key or config.get("api_key") or os.environ.get("DASHSCOPE_API_KEY")
            self.language_type = config.get("language_type") or language_type
        else:
            self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
            self.language_type = language_type
        self.config = config or {}
        self._config = kwargs
        self.base_url = base_url
        self.timeout = timeout
        self.provider = self.PROVIDER
        
    @property
    def available_voices(self) -> Dict[str, Voice]:
        return DASHSCOPE_TTS_VOICES.copy()
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def _build_payload(self, text: str, voice: str, **kwargs) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "input": {
                "text": text,
                "voice": voice,
                "language_type": kwargs.get("language_type", self.language_type),
            }
        }
    
    def _extract_audio_content(self, data: Dict, client: Union[httpx.Client, httpx.AsyncClient, None] = None) -> tuple:
        """Extract audio content from API response.
        
        Returns (audio_content, audio_format) tuple.
        """
        output = data.get("output", {})
        audio_info = output.get("audio", {})
        
        audio_url = None
        audio_base64 = None
        
        if isinstance(audio_info, dict):
            audio_url = audio_info.get("url")
            audio_base64 = audio_info.get("data") if audio_info.get("data") else None
        elif isinstance(audio_info, str):
            audio_base64 = audio_info
        
        audio_content = None
        audio_format = "wav"
        content_type = "audio/wav"
        
        if audio_url and ".mp3" in audio_url:
            audio_format = "mp3"
            content_type = "audio/mpeg"
        elif isinstance(audio_info, dict):
            fmt = audio_info.get("format", audio_format)
            if fmt == "mp3":
                audio_format = "mp3"
                content_type = "audio/mpeg"
        
        return audio_url, audio_base64, audio_format, content_type
    
    def generate_speech(
        self,
        text: str,
        voice: str = DEFAULT_DASHSCOPE_VOICE,
        output_file: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ) -> AudioResponse:
        """Generate speech synchronously."""
        if not self.api_key:
            raise ValueError("DashScope API key not configured")
        
        payload = self._build_payload(text, voice, **kwargs)
        logger.debug(f"DashScope TTS request: model={self.model_name}, voice={voice}")
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.API_ENDPOINT,
                    json=payload,
                    headers=self._get_headers(),
                )
                
                if response.status_code == 429:
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
                    raise RuntimeError(f"DashScope TTS API error: {response.status_code} - {error_msg}")
                
                data = response.json()
                logger.debug(f"DashScope TTS raw response keys: {data.keys()}")
                
                audio_url, audio_base64, audio_format, content_type = self._extract_audio_content(data)
                
                audio_content = None
                if audio_url:
                    logger.debug(f"Downloading audio from URL: {audio_url}")
                    audio_response = client.get(audio_url)
                    if audio_response.status_code == 200:
                        audio_content = audio_response.content
                    else:
                        raise RuntimeError(f"Failed to download audio: {audio_response.status_code}")
                elif audio_base64:
                    audio_content = base64.b64decode(audio_base64)
                
                if not audio_content:
                    raise RuntimeError(f"DashScope TTS response missing audio data")
                
                logger.debug(f"DashScope TTS generated {len(audio_content)} bytes of audio")
                
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
        """Generate speech asynchronously."""
        if not self.api_key:
            raise ValueError("DashScope API key not configured")
        
        payload = self._build_payload(text, voice, **kwargs)
        logger.debug(f"DashScope TTS request: model={self.model_name}, voice={voice}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.API_ENDPOINT,
                    json=payload,
                    headers=self._get_headers(),
                )
                
                if response.status_code == 429:
                    logger.warning("DashScope TTS rate limit hit, waiting 2 seconds...")
                    await asyncio.sleep(2)
                    response = await client.post(
                        self.API_ENDPOINT,
                        json=payload,
                        headers=self._get_headers(),
                    )
                
                if response.status_code != 200:
                    error_msg = response.text[:500] if response.text else "Unknown error"
                    raise RuntimeError(f"DashScope TTS API error: {response.status_code} - {error_msg}")
                
                data = response.json()
                logger.debug(f"DashScope TTS raw response keys: {data.keys()}")
                
                audio_url, audio_base64, audio_format, content_type = self._extract_audio_content(data)
                
                audio_content = None
                if audio_url:
                    logger.debug(f"Downloading audio from URL: {audio_url}")
                    audio_response = await client.get(audio_url)
                    if audio_response.status_code == 200:
                        audio_content = audio_response.content
                    else:
                        raise RuntimeError(f"Failed to download audio: {audio_response.status_code}")
                elif audio_base64:
                    audio_content = base64.b64decode(audio_base64)
                
                if not audio_content:
                    raise RuntimeError(f"DashScope TTS response missing audio data")
                
                logger.debug(f"DashScope TTS generated {len(audio_content)} bytes of audio")
                
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
                
        except httpx.TimeoutException:
            raise RuntimeError("DashScope TTS request timed out")
        except httpx.RequestError as e:
            raise RuntimeError(f"DashScope TTS request failed: {str(e)}")
    
    def _get_models(self) -> List:
        return []


# Backward compatibility aliases
BailianTextToSpeech = DashScopeTextToSpeech
BAILIAN_VOICES = DASHSCOPE_TTS_VOICES
DEFAULT_BAILIAN_VOICE = DEFAULT_DASHSCOPE_VOICE


def create_bailian_tts(
    model_name: str,
    config: Optional[Dict[str, Any]] = None,
) -> DashScopeTextToSpeech:
    config = config or {}
    return DashScopeTextToSpeech(
        model_name=model_name,
        api_key=config.get("api_key"),
        language_type=config.get("language_type", "Chinese"),
        **{k: v for k, v in config.items() if k not in ("api_key", "language_type")},
    )
