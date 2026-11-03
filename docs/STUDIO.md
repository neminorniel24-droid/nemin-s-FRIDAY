# The NEMIII Studio

Free, offline models and creative tools, stored on **one folder of your external SSD**. Nothing is
downloaded until you point NEMIII at that folder.

## What fits an RTX 4050 (6 GB) laptop

| Job | Model | Size | Runs on | Status |
|---|---|---|---|---|
| Chat brain | Llama 3.2 3B, Qwen 2.5 7B | 2 / 4.7 GB | GPU (Ollama) | automatic |
| Vision | Moondream, Gemma 3 4B | 1.7 / 3.3 GB | GPU (Ollama) | automatic |
| Speech to text | Whisper small (faster-whisper) | 0.5 GB | CPU | automatic |
| Text to speech | Kokoro 82M | 0.34 GB | CPU | automatic |
| Pictures | SDXL Turbo through ComfyUI | 6.9 GB | GPU, low-VRAM mode | automatic |
| Music | MusicGen small | 2.4 GB | GPU or CPU | automatic |
| Video | Wan 2.1 1.3B, LTX-Video | 9-10 GB | GPU, very slow | **manual**, inside ComfyUI |
| 3D | TripoSR | 1.5 GB | GPU | **manual** |

Honest limits: 6 GB of video memory is small. Pictures and music work well. Video comes out as short,
low-resolution clips and takes minutes. 3D is possible but fiddly. "Every model" cannot fit on any
drive, so the catalog is small on purpose. You can remove one to make room for another.

## Set up (once)

1. Plug in the SSD and find it: `ls /mnt` (a drive D: appears as `/mnt/d`).
2. Choose a folder on it and run the parts you want:

```bash
bash scripts/studio-setup.sh /mnt/d/NemiiiStudio                 # folders + settings (tiny)
bash scripts/studio-setup.sh /mnt/d/NemiiiStudio --tools         # voice, music, transcribe tools
bash scripts/studio-setup.sh /mnt/d/NemiiiStudio --comfy         # picture engine
bash scripts/studio-setup.sh /mnt/d/NemiiiStudio --ollama        # Ollama keeps its models on the SSD
```

Everything heavy (Python libraries, ComfyUI, caches) goes on the SSD, not on your laptop drive.
Restart NEMIII (`./stop.sh && ./run.sh`).

3. Download models by voice or typing. She asks you to confirm each download:

> "Studio status" · "Install the image model" · "Install Whisper" · "Install the Kokoro voice" ·
> "Install MusicGen" · "Delete the image model"

4. For pictures, start ComfyUI first: `bash scripts/studio-start.sh` (stop it with `studio-stop.sh`
   to free your graphics memory).

## Using it

> "Draw a neon city at night" · "Make 15 seconds of calm lo-fi piano" · "Say 'good morning team' as an audio file" ·
> "Transcribe my lecture recording" · "Open the picture you made" · "Read the transcript"

Creations run in the background, one at a time (6 GB cannot do two). You get a Windows notification
when one is ready. Everything lands in `outputs/` on the SSD: `images`, `music`, `speech`, `transcripts`.
The STUDIO tab of the side panel (`P`) shows free space and what is installed.

## Progress, viewer and voice (v17)

- **Progress bar:** while she makes something you see what she is doing and how far along it is. Pictures show the real step
  ("drawing, step 3 of 4"), music and transcripts show a real percentage.
- **Creations viewer:** when it is ready the viewer opens over the orb with the picture, an audio player, or the transcript.
  Say "show my creations" or press `F`. Older and newer buttons, thumbnails, and OPEN IN WINDOWS.
- **Natural voice:** with the Kokoro voice installed, everything she says uses it (the NATURAL / BROWSER button switches).
  If it ever fails she falls back to the browser voice by herself. Each mode has its own voice and speed.
- **Pause and stop:** while she talks you get PAUSE / RESUME and STOP buttons (`K` and Space).
- She never reads symbols, links or file paths out loud. The screen still shows the full written text.

## Safety

- She can only install ids from the catalog. A model can never give her a URL or a command.
- Installing and deleting always ask first.
- A download is refused if it would leave less than `MIN_FREE_GB` (default 3) free on the SSD.
- Deleting never touches anything outside the studio folder.
- If the SSD is unplugged she says so instead of failing strangely.

## If something is wrong

- **"I can't see the studio folder"**: the SSD is unplugged or got a new drive letter. Re-run setup with the new path.
- **"ComfyUI isn't running"**: `bash scripts/studio-start.sh`, then wait about a minute; log is `logs/comfyui.log`.
- **Picture out of memory**: close games and browsers, or stop Ollama models with `ollama stop <model>`.
- **Slow first picture**: the first run loads a 7 GB model from the SSD. Later ones take seconds. A USB 3 SSD is much better than USB 2.
- **SSD format**: NTFS works. exFAT works too (the setup uses copies instead of links).

Licences: SDXL Turbo and MusicGen weights have non-commercial terms. Fine for personal use; read them before selling anything you make.
