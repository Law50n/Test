import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

FORMATS = {
    "short": (1080, 1920),
    "long": (1920, 1080),
}


@dataclass
class Config:
    pexels_api_key: str
    tts_engine: str
    tts_voice: str
    video_format: str
    piper_model_path: str
    piper_speaker_id: int
    piper_sentence_silence: float

    @property
    def size(self) -> tuple[int, int]:
        return FORMATS[self.video_format]

    @classmethod
    def load(cls) -> "Config":
        video_format = os.environ.get("VIDEO_FORMAT", "short")
        if video_format not in FORMATS:
            raise ValueError(f"VIDEO_FORMAT must be one of {list(FORMATS)}, got {video_format!r}")
        return cls(
            pexels_api_key=os.environ.get("PEXELS_API_KEY", "").strip(),
            tts_engine=os.environ.get("TTS_ENGINE", "edge").strip(),
            tts_voice=os.environ.get("TTS_VOICE", "en-US-GuyNeural").strip(),
            video_format=video_format,
            piper_model_path=os.environ.get("PIPER_MODEL_PATH", "voices/en-us-libritts-high.onnx").strip(),
            piper_speaker_id=int(os.environ.get("PIPER_SPEAKER_ID", "90")),
            piper_sentence_silence=float(os.environ.get("PIPER_SENTENCE_SILENCE", "0.35")),
        )
