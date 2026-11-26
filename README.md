> Our life is like a pool of time. Time flows constantly, reducing the water level. Thinking about this core philosophy, I built this app, Time Pool, to help keep track on the time leaked and divide them for future plans.

# Time Pool

**English** · [简体中文](README.zh-CN.md)

Time Pool is a desktop app for keeping a local record of how you spend your time. Enter activities by hand or dictate a note in English or Mandarin. See the breakdown by category, from a single day to a full year. I first had the idea for Time Pool one morning in the spring of 2026, when I was in ninth grade preparing for China's high school entrance exam (the Zhongkao).

## Get Started on Windows

**Windows x64 · Single executable · No Python or Conda required**

From the GitHub release **Assets**, download `TimePool.exe` and double-click it. A local build puts the same file in `dist/TimePool.exe`. No installer, account, API key, or speech model is required for manual tracking.

Want to explore before adding your own records? Open PowerShell in the folder containing the EXE:

```powershell
.\TimePool.exe --demo
```

The demo includes six weeks of sample records. Its records and settings are separate from your regular profile and are removed on normal exit. The interface starts in English; switch to Simplified Chinese under **Interface language** in the sidebar.

## Track and Review Time

- Add, edit, delete, or backfill activities under categories and subcategories. Records are stored in whole minutes and cannot exceed 24 hours per day.
- View daily, weekly, monthly, quarterly, and yearly totals. Switch between bar and pie charts or click a category to see its subcategories.
- See time left unallocated. For past days this is labeled `timeleak`, calculated from logged time rather than stored as a separate record.

## Dictate a Note

1. In **AI quick entry**, click **Download model**. English and Mandarin share one [Whisper Base](https://huggingface.co/Systran/faster-whisper-base) download of about 148 MB, kept separate from the EXE.
2. Choose **Auto detect**, **English**, or **Mandarin**. Click **Record locally**, speak for up to two minutes, then click **Stop and transcribe**.
3. Edit the resulting text. To turn the note into dated time entries, configure an LLM in **Settings**, click **Preview entries**, then review and save.

Once the model is installed, microphone transcription runs offline on the CPU. Recordings stay in memory and are not uploaded. Sending a note to an LLM is a separate, optional action.

| Optional service | What it does |
| --- | --- |
| **LLM** | Extracts activities, dates, and durations from a note through an OpenAI-compatible `/chat/completions` endpoint. |
| **File STT** | Sends a selected audio file to an OpenAI-compatible `/audio/transcriptions` endpoint. |
| **External STT** | Receives transcript text from a WebSocket service you run or configure. It does not capture your microphone. |

No external services are bundled. A connection error in **External STT** does not affect **Record locally**. If the microphone does not open, check the default input device and desktop app microphone permissions in Windows.

## Data and Privacy

The EXE stores data under `%LOCALAPPDATA%\Time Pool`; running from source uses the repository directory. The EXE does not automatically import your source-run records or settings.

| File or folder | Contents |
| --- | --- |
| `time_pool_data.json` | Activity records |
| `time_pool_settings.json` | Interface preferences and API settings |
| `backup/` | Full data snapshots, at most once per day when the app detects a date rollover on startup or before that day's first record change |
| `.timepool_models/` | Downloaded speech model |

These files are not tracked by Git. Keys entered in Settings are stored as plain text; use the environment-variable field to keep them out of the settings file. There is no multi-device sync yet.

## Run or Build from Source

On Windows with Conda, run [`prepare_anaconda_env.bat`](prepare_anaconda_env.bat) once, then use [`try_timepool.bat`](try_timepool.bat) for sample data or [`run_timepool.bat`](run_timepool.bat) for regular use. If setup fails, check `prepare_anaconda_env.log`.

Alternatively, run or rebuild the app from the repository root in an activated Windows x64 Python 3.12 environment:

```powershell
# Run from source
python -m pip install -r requirements.txt
python main.py --demo
python -m unittest discover -s tests

# Build the standalone executable
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm TimePool.spec
```

The [build spec](TimePool.spec) produces `dist/TimePool.exe`. For a GitHub release, attach the EXE and, optionally, its SHA-256 checksum as release assets rather than committing files from `dist/`.

Time Pool uses PySide6 for the desktop interface, Matplotlib for charts, and faster-whisper for offline transcription.
