from PyInstaller.utils.hooks import check_requirement, collect_data_files, collect_dynamic_libs, copy_metadata


speech_data = collect_data_files("faster_whisper", includes=["assets/*.onnx"])
if check_requirement("hf-xet"):
    speech_data += copy_metadata("hf-xet")


app = Analysis(
    ["main.py"],
    binaries=collect_dynamic_libs("ctranslate2"),
    datas=speech_data,
    hiddenimports=["huggingface_hub._snapshot_download"],
    excludes=["PyQt6", "PyQt5", "PySide2"],
    hooksconfig={"matplotlib": {"backends": ["QtAgg"]}},
)

exe = EXE(
    PYZ(app.pure),
    app.scripts,
    app.binaries,
    app.datas,
    name="TimePool",
    console=False,
    upx=False,
)
