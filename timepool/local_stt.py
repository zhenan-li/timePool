from __future__ import annotations

from pathlib import Path

from .i18n import tr
from .microphone import RecordedAudio
from .paths import user_data_root


MODEL_REPO = "Systran/faster-whisper-base"
MODEL_REVISION = "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"
MODEL_CACHE = user_data_root() / ".timepool_models"
MODEL_FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt")
SPEECH_LANGUAGES = ("auto", "en", "zh")


class NoSpeechError(RuntimeError):
    pass


def _whisper_samples(audio: RecordedAudio):
    import av
    import numpy as np

    pcm = np.frombuffer(audio.pcm, dtype=np.int16)
    if not pcm.size:
        return np.empty(0, dtype=np.float32)
    frame = av.AudioFrame.from_ndarray(pcm.reshape(1, -1), format="s16", layout="mono")
    frame.sample_rate = audio.sample_rate
    resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
    frames = resampler.resample(frame) + resampler.resample(None)
    return np.concatenate([item.to_ndarray().ravel() for item in frames]) if frames else np.empty(0, dtype=np.float32)


class LocalTranscriber:
    def __init__(self, cache: Path = MODEL_CACHE) -> None:
        self._cache = cache
        self._model = None

    def _model_path(self) -> Path:
        repo_dir = "models--" + MODEL_REPO.replace("/", "--")
        return self._cache / repo_dir / "snapshots" / MODEL_REVISION

    def model_cached(self) -> bool:
        return all((self._model_path() / name).is_file() for name in MODEL_FILES)

    def download_model(self) -> None:
        if self.model_cached():
            return
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise RuntimeError(tr("Local transcription support is missing from this installation.")) from exc
        try:
            snapshot_download(
                MODEL_REPO,
                cache_dir=self._cache,
                revision=MODEL_REVISION,
                allow_patterns=MODEL_FILES,
                token=False,
            )
        except Exception as exc:
            raise RuntimeError(tr("Model download failed. Check your connection to Hugging Face. {error}", error=exc)) from exc
        if not self.model_cached():
            raise RuntimeError(tr("The download is incomplete. Try downloading the model again."))

    def load_model(self):
        if self._model is not None:
            return self._model
        if not self.model_cached():
            raise RuntimeError(tr("Download the speech model from the main window first."))
        try:
            from faster_whisper import WhisperModel
        except (ImportError, OSError) as exc:
            raise RuntimeError(tr("Local transcription support is missing from this installation.")) from exc

        self._model = WhisperModel(str(self._model_path()), device="cpu", compute_type="int8", local_files_only=True)
        return self._model

    def transcribe(self, audio: RecordedAudio, language: str = "auto") -> str:
        if language not in SPEECH_LANGUAGES:
            raise ValueError(f"Unsupported speech language: {language}")
        model = self.load_model()
        # The microphone already provides PCM, so no container decoder is needed.
        samples = _whisper_samples(audio)
        transcript = ""
        if samples.size:
            segments, _ = model.transcribe(samples, language=None if language == "auto" else language, vad_filter=True, beam_size=3)
            transcript = "".join(part.text for part in segments).strip()
        if not transcript:
            raise NoSpeechError(tr("No speech was detected."))
        return transcript
