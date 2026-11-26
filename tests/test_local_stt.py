import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from timepool.local_stt import MODEL_FILES, MODEL_REPO, MODEL_REVISION, LocalTranscriber, NoSpeechError, _whisper_samples
from timepool.microphone import MicrophoneRecorder, RecordedAudio


class MicrophoneTests(unittest.TestCase):
    def fake_device(self):
        stream = Mock()
        stream.active = True
        return SimpleNamespace(
            query_devices=Mock(return_value={"default_samplerate": 48000}),
            RawInputStream=Mock(return_value=stream),
        )

    def test_records_pcm_and_releases_microphone(self):
        recorder = MicrophoneRecorder()
        device = self.fake_device()
        with patch.dict(sys.modules, {"sounddevice": device}):
            recorder.start()
            callback = device.RawInputStream.call_args.kwargs["callback"]
            pcm = b"\x01\x02" * 24000
            callback(pcm, 24000, None, None)
            clip = recorder.stop()

        self.assertFalse(recorder.active)
        device.RawInputStream.return_value.close.assert_called_once()
        self.assertEqual(clip, RecordedAudio(48000, pcm))

    def test_cancel_clears_audio_and_empty_recording_fails(self):
        recorder = MicrophoneRecorder()
        with patch.dict(sys.modules, {"sounddevice": self.fake_device()}):
            recorder.start()
            recorder._capture(b"\x00\x01" * 24000, 24000, None, None)
            recorder.cancel()
            recorder.start()
            with self.assertRaises(RuntimeError):
                recorder.stop()
            self.assertFalse(recorder.active)

    def test_audio_buffer_obeys_duration_limit(self):
        recorder = MicrophoneRecorder()
        with patch.dict(sys.modules, {"sounddevice": self.fake_device()}):
            recorder.start()
            with patch("timepool.microphone.MAX_RECORDING_SECONDS", 1):
                recorder._capture(b"\x00\x01" * 50000, 50000, None, None)
            self.assertEqual(len(recorder.stop().pcm), 96000)


class LocalTranscriberTests(unittest.TestCase):
    def test_download_only_runs_on_explicit_request(self):
        with tempfile.TemporaryDirectory() as directory:
            transcriber = LocalTranscriber(Path(directory))
            model_path = transcriber._model_path()

            def install_files(*_args, **_kwargs):
                model_path.mkdir(parents=True)
                for name in MODEL_FILES:
                    (model_path / name).touch()

            with patch("huggingface_hub.snapshot_download", side_effect=install_files) as download:
                with self.assertRaisesRegex(RuntimeError, "Download the speech model"):
                    transcriber.load_model()
                download.assert_not_called()
                transcriber.download_model()
                transcriber.download_model()
                download.assert_called_once_with(
                    MODEL_REPO, cache_dir=Path(directory), revision=MODEL_REVISION,
                    allow_patterns=MODEL_FILES, token=False,
                )
            self.assertTrue(transcriber.model_cached())

    def test_resamples_pcm_to_normalized_16khz_mono(self):
        audio = RecordedAudio(48000, b"\x00\x40" * 48000)
        samples = _whisper_samples(audio)
        self.assertEqual(samples.shape, (16000,))
        self.assertEqual(samples.dtype.name, "float32")
        self.assertAlmostEqual(float(samples[8000]), 0.5, places=4)

    def test_cached_model_loads_once_without_download_and_transcribes(self):
        with tempfile.TemporaryDirectory() as directory:
            transcriber = LocalTranscriber(Path(directory))
            model_path = transcriber._model_path()
            model_path.mkdir(parents=True)
            for name in MODEL_FILES[:-1]:
                (model_path / name).touch()
            self.assertFalse(transcriber.model_cached())
            (model_path / MODEL_FILES[-1]).touch()

            download = Mock()
            model_factory = Mock()
            model = model_factory.return_value
            model.transcribe.return_value = ([SimpleNamespace(text=" first"), SimpleNamespace(text=" second ")], None)
            modules = {
                "faster_whisper": SimpleNamespace(WhisperModel=model_factory),
                "faster_whisper.utils": SimpleNamespace(download_model=download),
            }
            with patch.dict(sys.modules, modules):
                self.assertIs(transcriber.load_model(), model)
            clip = RecordedAudio(16000, b"\x00\x00")
            for language, expected in (("en", "en"), ("zh", "zh"), ("auto", None)):
                self.assertEqual(transcriber.transcribe(clip, language), "first second")
                self.assertEqual(model.transcribe.call_args.kwargs["language"], expected)
            download.assert_not_called()
            model_factory.assert_called_once_with(str(model_path), device="cpu", compute_type="int8", local_files_only=True)
            self.assertTrue(model.transcribe.call_args.kwargs["vad_filter"])

    def test_no_speech_does_not_return_a_transcript(self):
        transcriber = LocalTranscriber()
        with patch.object(transcriber, "load_model") as load:
            load.return_value.transcribe.return_value = ([], None)
            with self.assertRaises(NoSpeechError):
                transcriber.transcribe(RecordedAudio(16000, b"\x00\x00"))
