from .i18n import tr


from dataclasses import dataclass


MAX_RECORDING_SECONDS = 120
SAMPLE_BYTES = 2


@dataclass(frozen=True, slots=True)
class RecordedAudio:
    sample_rate: int
    pcm: bytes


class MicrophoneRecorder:
    def __init__(self) -> None:
        self._stream = None
        self._pcm = bytearray()
        self._sample_rate = 0

    @property
    def active(self) -> bool:
        return self._stream is not None and self._stream.active

    def start(self) -> None:
        if self._stream is not None:
            raise RuntimeError(tr("Recording is already active."))
        try:
            import sounddevice as sd
        except (ImportError, OSError) as exc:
            raise RuntimeError(tr("Microphone support is missing from this installation.")) from exc

        try:
            self._sample_rate = round(sd.query_devices(kind="input")["default_samplerate"])
            self._pcm.clear()
            self._stream = sd.RawInputStream(
                samplerate=self._sample_rate, channels=1, dtype="int16", callback=self._capture
            )
            self._stream.start()
        except Exception as exc:
            self.cancel()
            raise RuntimeError(tr("Could not open the default microphone. Check the input device and microphone permissions. {error}", error=exc)) from exc

    def _capture(self, data, _frames, _timing, _status) -> None:
        limit = MAX_RECORDING_SECONDS * self._sample_rate * SAMPLE_BYTES
        remaining = limit - len(self._pcm)
        if remaining > 0:
            self._pcm.extend(memoryview(data)[:remaining])

    def stop(self) -> RecordedAudio:
        try:
            self._close_stream()
            if len(self._pcm) < self._sample_rate * SAMPLE_BYTES // 3 or not self._pcm:
                raise RuntimeError(tr("The recording was too short or received no audio. Try again."))
            return RecordedAudio(self._sample_rate, bytes(self._pcm))
        finally:
            self._pcm.clear()

    def cancel(self) -> None:
        try:
            self._close_stream()
        finally:
            self._pcm.clear()

    def _close_stream(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.close(ignore_errors=True)
