import json
import sys
import traceback
from pathlib import Path
from tempfile import TemporaryDirectory


def check_runtime(app, report_path: Path) -> int:
    from .demo import seed_demo_data
    from .local_stt import LocalTranscriber, NoSpeechError, _whisper_samples
    from .main_window import MainWindow
    from .microphone import RecordedAudio
    from .paths import user_data_root
    from .utils import today_local

    report = {"frozen": getattr(sys, "frozen", False), "data_root": str(user_data_root())}
    try:
        import sounddevice
        from faster_whisper.vad import get_vad_model
        from huggingface_hub import snapshot_download
        from huggingface_hub.utils.tqdm import tqdm

        with TemporaryDirectory(prefix="timepool-check-") as directory:
            root = Path(directory)
            seed_demo_data(root, today_local())
            window = MainWindow(root, demo=True)
            window.show()
            app.processEvents()
            window.chart.canvas.draw()
            if window.tree.topLevelItemCount() < 2:
                raise RuntimeError("The trial did not render its sample records.")
            window.close()

        speech = LocalTranscriber()
        silence = RecordedAudio(48000, bytes(96000))
        if _whisper_samples(silence).size != 16000:
            raise RuntimeError("Unexpected audio resampling result.")
        get_vad_model()
        report["portaudio_version"] = sounddevice.get_portaudio_version()[1]
        report["downloader_available"] = callable(snapshot_download)
        with tqdm(total=1) as download_progress:
            download_progress.update(1)
        report["cached_model_checked"] = speech.model_cached()
        if report["cached_model_checked"]:
            try:
                speech.transcribe(silence)
            except NoSpeechError:
                pass
            else:
                raise RuntimeError("The speech model returned text for silence.")
        report["ok"] = True
    except Exception:
        report.update(ok=False, error=traceback.format_exc())

    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1
