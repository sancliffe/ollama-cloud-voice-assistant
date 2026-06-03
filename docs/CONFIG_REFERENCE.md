# ollama-STT-TTS Configuration Reference

This guide explains all configuration options for the ollama-STT-TTS voice assistant when using the GKE cloud backend.

## Quick Start Configuration

```ini
[Models]
# Must match what's seeded in gke-ollama-spot-ai backend
ollama_model = gemma2:2b         # Recommended (fast, cheap)
# ollama_model = llama3           # Alternative (larger, slower)

# Cloud backend instead of localhost
ollama_host = http://ollama.gke.dev
ollama_timeout = 120             # Seconds (allow 2-4 min for cold-start)

# Local speech processing (runs on your machine)
whisper_model = base.en          # STT: tiny, base, small, medium
piper_model = en_US-libritts_r   # TTS voice model
wakeword = hey_jarvis            # Wake word detection

[Audio]
device_index = 0                 # Microphone (find with: python run.py --list-devices)
piper_output_device_index = 0    # Speaker (find with: python run.py --list-output-devices)
sample_rate = 16000              # For Whisper
chunk_size = 2048                # Audio processing chunk

[Functionality]
wakeword_threshold = 0.5         # 0.0-1.0 (lower = more sensitive)
vad_aggressiveness = 2           # 0-3 (silence detection)
conversation_history_length = 5  # Multi-turn chat context

[LLM]
temperature = 0.7                # 0.0-1.0 (0=factual, 1=creative)
max_tokens = 512                 # Response length

[Logging]
log_level = INFO                 # DEBUG, INFO, WARNING, ERROR
console_output = True            # Print to terminal

[Performance]
enable_audio_preprocessing = true
enable_vad = true
streaming = true                 # Token-by-token responses
use_faster_whisper = true        # Use GPU if available
```

## Detailed Option Reference

### `[Models]` Section

| Option | Values | Description | Example |
|--------|--------|-------------|---------|
| `ollama_model` | Model name | LLM to use for chat | `gemma2:2b`, `llama3`, `mistral` |
| `ollama_host` | URL | Ollama API endpoint | `http://ollama.gke.dev` (cloud) |
| `ollama_timeout` | Seconds | HTTP request timeout | `120` (allow cold-start) |
| `whisper_model` | Size | STT model | `base.en`, `tiny.en`, `small.en` |
| `piper_model` | Voice | TTS voice model | `en_US-libritts_r`, `en_GB-alan` |
| `wakeword` | Phrase | Wake word for detection | `hey_jarvis`, `ok_google`, `hey_siri` |

### `[Audio]` Section

| Option | Range | Description |
|--------|-------|-------------|
| `device_index` | 0-N | Microphone device ID (find with `--list-devices`) |
| `piper_output_device_index` | 0-N | Speaker device ID (find with `--list-output-devices`) |
| `sample_rate` | Hz | Audio sample rate (16000 for Whisper) |
| `chunk_size` | Samples | Audio processing chunk (1024-4096) |

### `[Functionality]` Section

| Option | Range | Description |
|--------|-------|-------------|
| `wakeword_threshold` | 0.0-1.0 | Lower = more sensitive (more false positives) |
| `vad_aggressiveness` | 0-3 | Higher = better silence detection |
| `conversation_history_length` | 1-20 | Previous messages for context |
| `system_prompt` | Text or path | Custom system prompt for the LLM |

### `[LLM]` Section

| Option | Range | Description |
|--------|-------|-------------|
| `temperature` | 0.0-1.0 | 0 = deterministic, 1 = creative |
| `max_tokens` | 1-2048 | Max response length (tokens) |
| `top_p` | 0.0-1.0 | Nucleus sampling (diversity) |

### `[Logging]` Section

| Option | Values | Description |
|--------|--------|-------------|
| `log_level` | DEBUG, INFO, WARNING, ERROR | Verbosity level |
| `log_file` | Path | Where to save logs |
| `console_output` | true, false | Also print to terminal |

### `[Performance]` Section

| Option | Values | Description |
|--------|--------|-------------|
| `enable_audio_preprocessing` | true, false | Noise reduction |
| `noise_threshold` | 0.0-1.0 | How aggressive noise reduction |
| `enable_vad` | true, false | Voice activity detection (silence) |
| `streaming` | true, false | Token-by-token response streaming |
| `use_faster_whisper` | true, false | Use GPU-optimized Whisper |

## Finding Audio Device IDs

```bash
# List all input devices (microphones)
python run.py --list-devices

# List all output devices (speakers)
python run.py --list-output-devices

# Example output:
# Input Devices:
# 0: Built-in Microphone (Primary)
# 1: USB Microphone
# 2: HDMI Audio In
#
# Output Devices:
# 0: Speaker
# 1: HDMI
# 2: USB Audio Out
```

Then set in `config.ini`:
```ini
[Audio]
device_index = 1              # Use USB Microphone
piper_output_device_index = 0 # Use Speaker
```

## Cloud vs. Local Configuration

### For Cloud Backend (GKE)

```ini
[Models]
ollama_host = http://ollama.gke.dev    # Cloud backend
ollama_timeout = 120                   # Allow cold-start time
ollama_model = gemma2:2b               # Match GKE seed
```

**Cold-start timeline:**
- First request: 2-4 minutes (cluster provisioning)
- Subsequent requests within 5 minutes: < 1 second
- After 5+ minutes idle: Cold-start again (KEDA scales to 0)

### For Local Backend (localhost)

```ini
[Models]
ollama_host = http://localhost:11434   # Local Ollama
ollama_timeout = 30                    # Shorter timeout (no cold-start)
ollama_model = llama3                  # Whatever you have locally
```

## Model Selection Guide

### STT (Speech-to-Text) Models

| Model | Size | Speed | Accuracy | Recommended For |
|-------|------|-------|----------|-----------------|
| `tiny.en` | 39MB | Very Fast | Basic | Low-power devices, real-time |
| `base.en` | 140MB | Fast | Good | Most use cases (default) |
| `small.en` | 244MB | Medium | Better | Noisy environments |
| `medium.en` | 769MB | Slow | Best | Maximum accuracy |

### TTS (Text-to-Speech) Models

| Voice | Gender | Accent | Quality | Speed |
|-------|--------|--------|---------|-------|
| `en_US-libritts_r` | Female | Neutral | Good | Fast |
| `en_US-arpa` | Female | American | High | Medium |
| `en_GB-alan` | Male | British | High | Medium |

See full list: https://github.com/rhasspy/piper#-models

### LLM Models (via Ollama)

| Model | Size | Speed | Quality | Cost | Recommended |
|-------|------|-------|---------|------|-------------|
| `gemma2:2b` | 2GB | Fast | Good | Low | ✓ Best for cloud |
| `llama3` | 7GB | Medium | Better | Medium | ✓ Local use |
| `mistral` | 7B | Medium | Good | Medium | ✓ Fast reasoning |
| `neural-chat` | 7B | Medium | Very Good | Medium | ✓ Conversational |

## Troubleshooting Configuration

### "Connection refused to ollama.gke.dev"

Check `ollama_host` in `[Models]`:
```ini
ollama_host = http://ollama.gke.dev  # Correct
# NOT: http://localhost:11434
# NOT: http://127.0.0.1:11434
```

### "Timeout waiting for model"

Increase `ollama_timeout` for cold-starts:
```ini
[Models]
ollama_timeout = 180  # 3 minutes instead of 2
```

### "Audio device not found"

Run to find correct IDs:
```bash
python run.py --list-devices
python run.py --list-output-devices
```

Then update:
```ini
[Audio]
device_index = [YOUR_MIC_ID]
piper_output_device_index = [YOUR_SPEAKER_ID]
```

### "Wake word not detected"

Adjust sensitivity:
```ini
[Functionality]
wakeword_threshold = 0.3  # More sensitive (may have false positives)
```

### "Slow responses or model crashes"

Try smaller model:
```ini
[Models]
ollama_model = gemma2:2b  # Instead of llama3
whisper_model = tiny.en   # Instead of base.en
```

## Advanced: Custom System Prompt

You can customize how the assistant behaves with a system prompt:

### Inline (in config.ini)
```ini
[Functionality]
system_prompt = You are a pirate captain named Jarvis. Answer all questions in pirate speak.
```

### From File
```ini
[Functionality]
system_prompt = /path/to/system_prompt.txt
```

**Example system_prompt.txt:**
```
You are a helpful voice assistant named Jarvis.
You are knowledgeable, friendly, and concise.
Keep responses to 2-3 sentences unless asked for more detail.
If asked something you don't know, say so honestly.
```

## Performance Tuning

### For Faster Responses

```ini
[LLM]
max_tokens = 256          # Shorter responses (faster)
temperature = 0.3         # More deterministic (faster)

[Functionality]
conversation_history_length = 2  # Less context to process

[Performance]
streaming = true          # Stream tokens for faster perceived response
```

### For Better Audio Quality

```ini
[Models]
whisper_model = small.en  # Better accuracy

[Audio]
chunk_size = 4096         # Larger chunks (less processing overhead)

[Performance]
enable_audio_preprocessing = true
noise_threshold = 0.05    # More aggressive noise removal
```

### For Lower Memory Usage

```ini
[Models]
whisper_model = tiny.en   # Minimal memory
ollama_model = gemma2:2b  # Small LLM

[Performance]
use_faster_whisper = false  # Use standard Whisper (more memory-efficient)
```

## Command-Line Overrides

Any config option can be overridden via command line:

```bash
# Override model
python run.py --ollama-model mistral

# Override audio devices
python run.py --device-index 1 --piper-output-device-index 2

# Override whisper model
python run.py --whisper-model small.en

# Override sensitivity
python run.py --wakeword-threshold 0.3 --vad-aggressiveness 3

# Enable debug
python run.py --debug

# Use custom system prompt
python run.py --system-prompt "You are a helpful assistant"

# Combine multiple overrides
python run.py --ollama-model llama3 --device-index 1 --debug
```

## Further Resources

- [ollama-STT-TTS GitHub](https://github.com/sancliffe/ollama-STT-TTS)
- [gke-ollama-spot-ai GitHub](https://github.com/sancliffe/gke-ollama-spot-ai)
- [Ollama Model Library](https://ollama.ai/library)
- [Faster Whisper Models](https://github.com/SYSTRAN/faster-whisper)
- [Piper TTS Voices](https://github.com/rhasspy/piper#-models)
- [OpenWakeWord Models](https://github.com/dscripka/openWakeWord#models)
