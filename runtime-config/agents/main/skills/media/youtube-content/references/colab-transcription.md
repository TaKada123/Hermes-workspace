# Colab transcription through MCP

## Local integration

- The default profile has custom MCP `colab`, checkout `/home/vottak/Проекты/hermes-colab-agent`, executable `.venv/bin/colab-mcp`, configured with `--browser-cdp-endpoint http://127.0.0.1:9222`.
- Launch ordinary `/usr/bin/google-chrome-stable` with `--user-data-dir=/home/vottak/.local/share/hermes-colab-agent/manual-chrome-profile --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222`. Verify listener is loopback-only. Keep the browser alive while using MCP.
- Google login can reject Playwright-launched Chromium. Let the user log into ordinary Chrome manually; never copy cookies or use their everyday profile. The dedicated manual profile persists login.
- Use an explicit user-provided `/drive/ID` notebook URL with `open_colab_browser_connection`; verify with `get_cells`. The fork's no-argument default `/notebooks/empty.ipynb` is rejected by its own URL validator; `/scratchpad` may return 403.
- Read-only `get_cells` is the minimum real connection check. Never infer notebook control from MCP discovery or page title.

## Transcription

- Preserve existing cells. Add separate task cells with explicit `cellIndex` and use exact IDs returned by `add_code_cell` (`newCellId`). Read back edits and outputs.
- Download the requested audio using yt-dlp in Colab. Record title, duration and path. Inspect errors: a JS-runtime warning need not mean download failed.
- Use faster-whisper large-v3 on existing GPU without enabling paid resources. Inspect actual CUDA availability and GPU model.
- Colab PyAV 19 can reject faster-whisper's `av.open(metadata_errors='ignore')`. Avoid monkey-patching: decode audio with ffmpeg `-f f32le -ac 1 -ar 16000 pipe:1`, convert stdout with `np.frombuffer(..., dtype=np.float32).copy()`, pass ndarray to `model.transcribe`.
- Colab may default to CUDA 13 while CTranslate2 expects libcublas.so.12. First discover installed library paths with glob; if CUDA 12 libs exist under site-packages/nvidia, preload libcublasLt.so.12 then libcublas.so.12 then libcudnn.so.9 via ctypes.CDLL(absolute_path, mode=ctypes.RTLD_GLOBAL). Keep handles alive. Do not reinstall CUDA blindly. Verify a short real GPU transcription before the full run.
- Flush plain/timestamped text per segment; store segment JSON and completion metadata. Check final speech timestamp against audio duration, not merely exit status. Label unedited output as automatic transcription; don't silently rewrite uncertain words.

## Export

- User prefers future video transcriptions delivered as Markdown `.md`, not plain `.txt`. Default to a readable Markdown transcript with title, source URL, and timestamps; keep raw JSON or TXT only as optional supporting artifacts.

- The fork's download_file helper may fail because its internal add_code_cell omits required cellIndex. Do not repeatedly retry it unchanged.
- Bundle transcript.txt, transcript_timestamped.txt, segments.json and metadata/completion JSON into ZIP; compute SHA256 in Colab.
- files.download may not produce a local file through this MCP/browser route; verify filesystem before claiming download.
- Reliable fallback: add an explicit-index export cell printing marker + base64 ZIP + end marker. Run via MCP. Large tool output is persisted under cache/spillover; parse the returned exact spillover path locally, decode base64, verify SHA256 against Colab, validate archive member names, then extract into a user-visible output directory. Do not re-fetch an already persisted large result.
- Keep reusable procedures here, not user notebook IDs or individual-video progress. Report absolute artifact paths in CLI. Close only the dedicated browser when asked, leaving Colab MCP configured in main.
