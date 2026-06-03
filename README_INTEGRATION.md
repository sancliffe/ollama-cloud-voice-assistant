# Complete Integration: gke-ollama-spot-ai + ollama-STT-TTS

## Overview

You're integrating two perfectly complementary open-source projects:

1. **`gke-ollama-spot-ai`** — Cost-optimized LLM backend on Google Cloud
   - Deploys Ollama on GKE Autopilot with KEDA autoscaling
   - Scales pods to zero when idle → ~$5-10/month cost
   - Cold-start: 2-4 minutes (cluster provisioning)
   - Warm inference: < 1 second

2. **`ollama-STT-TTS`** — Local voice interface (STT, TTS, wake word)
   - Runs entirely on your machine (no cloud dependencies for audio)
   - Uses Whisper for speech-to-text
   - Uses Piper for text-to-speech
   - Uses openwakeword for "Hey Jarvis" detection
   - Makes HTTP requests to cloud LLM backend

**Result:** A cost-effective, low-latency voice assistant that offloads expensive LLM inference to the cloud while keeping audio processing local.

---

## Quick Start (5 Commands)

```bash
# 1. Deploy GKE backend (15 min)
git clone https://github.com/sancliffe/gke-ollama-spot-ai.git && cd gke-ollama-spot-ai
./scripts/setup-cluster.sh
kubectl apply -f https://github.com/kedacore/keda/releases/download/v2.13.0/keda-2.13.0.yaml --server-side
helm repo add kedacore https://kedacore.github.io/charts && helm repo update && helm install http-add-on kedacore/keda-add-ons-http --namespace keda --create-namespace
kubectl apply -f k8s/ && ./scripts/seed-initial-model.sh

# 2. Get KEDA IP and update DNS (2 min)
export KEDA_IP=$(kubectl get svc -n keda keda-http-add-on-interceptor-proxy -o jsonpath='{.status.loadBalancer.ingress[0].ip}') && echo "$KEDA_IP ollama.gke.dev" | sudo tee -a /etc/hosts

# 3. Clone and setup voice frontend (5 min)
cd .. && git clone https://github.com/sancliffe/ollama-STT-TTS.git && cd ollama-STT-TTS
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# 4. Find audio devices and update config.ini (2 min)
python run.py --list-devices  # Note your microphone ID
python run.py --list-output-devices  # Note your speaker ID
# Edit config.ini: ollama_host = http://ollama.gke.dev, update device IDs

# 5. Pre-warm cluster and run (2-4 min wait + running)
curl http://ollama.gke.dev/api/tags && sleep 240 && python run.py
```

Then speak: "Hey jarvis, what's 2+2?"

---

## What Each Repository Does

### `gke-ollama-spot-ai` (The Brain)

**Purpose:** Runs Ollama LLM inference on cost-optimized GKE infrastructure

**How it works:**
1. Provisions GKE Autopilot cluster with Spot nodes
2. Deploys KEDA (Kubernetes autoscaling) with HTTP trigger
3. Scales Ollama pods from 0 to N based on incoming HTTP requests
4. Persists models in a 50GB volume
5. First request triggers 2-4 minute cluster provisioning
6. Subsequent requests within 5 minutes are sub-second

**Cost:** ~$5-10/month (only charges when actively processing)

**Models:** Configurable (gemma2:2b, llama3, mistral, etc.)

### `ollama-STT-TTS` (The Face)

**Purpose:** Local voice interface that talks to cloud LLM

**Components:**
- **Whisper (STT):** Converts speech to text (runs locally)
- **Piper (TTS):** Converts text to speech (runs locally)
- **openwakeword:** Detects "Hey Jarvis" phrase (runs locally)
- **webrtcvad:** Silence detection (knows when you stop talking)
- **Python HTTP client:** Makes API calls to `http://ollama.gke.dev`

**No cloud dependencies for audio processing** — all speech handling happens on your machine

---

## Integration Architecture

```
┌────────────────────────────────────────┐
│         Local Machine                   │
├────────────────────────────────────────┤
│                                         │
│   Python Voice Assistant                │
│   ├─ Whisper (STT) [LOCAL]             │
│   ├─ Piper (TTS) [LOCAL]               │
│   ├─ Wake Word Detection [LOCAL]       │
│   └─ HTTP Client →                      │
│       http://ollama.gke.dev             │
│       (automatic DNS resolution)        │
│                                         │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴──────┐
        │   Internet  │
        └──────┬──────┘
               │
┌──────────────▼──────────────────────────┐
│     Google Cloud Platform                │
├────────────────────────────────────────┤
│                                         │
│   KEDA HTTP Add-on                      │
│   ├─ Listens on port 80                │
│   ├─ Routes ollama.gke.dev requests    │
│   └─ Auto-scales pods on request       │
│       │                                 │
│       ▼                                 │
│   Ollama Pod(s)                         │
│   ├─ Model: gemma2:2b (or other)      │
│   ├─ Resources: 2 CPU, 4GB RAM         │
│   ├─ Storage: 50GB volume              │
│   ├─ Node: Spot VM (cheap)             │
│   ├─ Idle Behavior: Scales to 0 pods  │
│   └─ Cold Start: 2-4 minutes            │
│                                         │
└────────────────────────────────────────┘
```

---

## The Integration Documents

You now have complete documentation:

### 1. **INTEGRATION.md** — Main Guide
Start here. 5-step walkthrough:
1. Deploy gke-ollama-spot-ai backend
2. Configure DNS routing
3. Setup ollama-STT-TTS frontend
4. Understand cold starts
5. Run the voice assistant

### 2. **CONFIG_REFERENCE.md** — All Options Explained
Every configuration option for `config.ini`:
- Model selection (STT, TTS, LLM)
- Audio device configuration
- Wake word sensitivity
- Performance tuning
- Troubleshooting by config issue

### 3. **COLD_START_GUIDE.md** — Latency Management
Deep dive into the 2-4 minute "cold start" phenomenon:
- Why it happens (GCP provisioning Spot nodes)
- How to pre-warm the cluster
- Monitoring & debugging
- Cost-latency tradeoff explained

### 4. **QUICK_REFERENCE.md** — Cheat Sheet
Quick lookup:
- Essential commands
- Common errors & fixes
- Model comparison table
- Expected latencies

### 5. **frontend/config.ini** — Ready-to-Use Template
Pre-populated configuration with:
- `ollama_host = http://ollama.gke.dev` (cloud)
- Comments explaining each option
- Reasonable defaults

### 6. **bridge/connect-assistant.sh** — Automation Script
Automates DNS mapping and config updates:
```bash
cd bridge && ./connect-assistant.sh  # Requires sudo
```

---

## Key Decisions & Tradeoffs

### Model Choice

**Option 1: gemma2:2b (Recommended)**
- Size: 2GB
- Speed: Fast (~500ms)
- Cost: ~$0.003 per 1M tokens
- Quality: Good for general Q&A
```bash
# In gke-ollama-spot-ai/scripts/seed-initial-model.sh
ollama pull gemma2:2b
```

**Option 2: llama3 (Default)**
- Size: 7GB
- Speed: Medium (~2s)
- Cost: ~$0.015 per 1M tokens
- Quality: Better reasoning & knowledge
```bash
# Keep as-is or change to your preference
ollama pull llama3
```

**Important:** `config.ini: ollama_model` MUST match what you seed in GKE!

### Latency Acceptance

**Cold Start (First Request of Day):** 2-4 minutes
- GCP provisions Spot node
- Ollama pod starts
- Model loads from disk
- Request executes

**Warm Requests:** < 1 second
- Pod already running
- Fast inference

**Idle Scaling:** After 5 minutes of no requests, KEDA scales pod to 0 to save costs

This is the core tradeoff: You pay $0 during idle times but accept occasional wait.

### Audio Device Configuration

You must tell the assistant which microphone and speaker to use:

```bash
# Find device IDs
python run.py --list-devices         # Microphones
python run.py --list-output-devices  # Speakers

# Update config.ini
[Audio]
device_index = 1  # Your microphone (from list-devices)
piper_output_device_index = 0  # Your speaker (from list-output-devices)
```

---

## Common Issues & Solutions

### "Connection refused to ollama.gke.dev"
- Verify `/etc/hosts` has the KEDA IP
- Check DNS: `ping ollama.gke.dev`
- Re-run: `bridge/connect-assistant.sh`

### "Timeout on first request"
- This is normal (cold start: 2-4 minutes)
- Pre-warm: `curl http://ollama.gke.dev/api/tags`
- Wait for response, then use assistant

### "Model not found"
- Verify seeding completed: `kubectl logs -l app=ollama`
- Check model name in `config.ini` matches what you seeded
- Re-seed if needed: `./scripts/seed-initial-model.sh`

### "No microphone input"
- List devices: `python run.py --list-devices`
- Update `device_index` in `config.ini`
- Test: `python run.py --debug`

### "Pod won't start (Pending)"
- Check quota: `kubectl describe pod -l app=ollama`
- Try different region: `REGION=us-east1 ./scripts/setup-cluster.sh`
- Or wait (Spot capacity fluctuates)

See **CONFIG_REFERENCE.md** or **QUICK_REFERENCE.md** for more troubleshooting.

---

## Cost Analysis

| Scenario | Monthly Cost |
|----------|--------------|
| **Idle only (no daily usage)** | ~$5 (storage only) |
| **1 hour/day active** | ~$8-10 |
| **3 hours/day active** | ~$15-20 |
| **Always-on (comparison)** | ~$50-70 (GPU) or ~$20-30 (CPU) |

**Savings:** 85-90% vs. always-on GPU/CPU backends

---

## Step-by-Step: From Zero to Voice Assistant

### Phase 1: Deploy Backend (20 minutes)

```bash
# Clone backend
git clone https://github.com/sancliffe/gke-ollama-spot-ai.git
cd gke-ollama-spot-ai

# Provision GKE cluster
./scripts/setup-cluster.sh

# Install KEDA (Kubernetes autoscaling)
kubectl apply -f https://github.com/kedacore/keda/releases/download/v2.13.0/keda-2.13.0.yaml --server-side
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install http-add-on kedacore/keda-add-ons-http --namespace keda --create-namespace

# Deploy Ollama
kubectl apply -f k8s/

# Seed initial model (5-10 minutes)
./scripts/seed-initial-model.sh
```

### Phase 2: Configure DNS (2 minutes)

```bash
# Get KEDA IP
export KEDA_IP=$(kubectl get svc -n keda keda-http-add-on-interceptor-proxy \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Add to /etc/hosts
echo "$KEDA_IP ollama.gke.dev" | sudo tee -a /etc/hosts

# Verify
ping ollama.gke.dev
curl http://ollama.gke.dev/api/tags
```

### Phase 3: Setup Voice Assistant (10 minutes)

```bash
# Clone frontend
cd ..
git clone https://github.com/sancliffe/ollama-STT-TTS.git
cd ollama-STT-TTS

# Create Python environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install system dependencies (if needed)
# Linux: sudo apt-get install portaudio19-dev ffmpeg
# macOS: brew install portaudio ffmpeg
```

### Phase 4: Configure Audio (5 minutes)

```bash
# Find device IDs
python run.py --list-devices
python run.py --list-output-devices

# Edit config.ini
nano config.ini
# Update:
# - ollama_host = http://ollama.gke.dev
# - ollama_model = gemma2:2b  (or llama3)
# - device_index = [YOUR_MIC]
# - piper_output_device_index = [YOUR_SPEAKER]
```

### Phase 5: Pre-warm & Run (5-10 minutes)

```bash
# Pre-warm cluster (2-4 minute wait)
curl http://ollama.gke.dev/api/tags
# Wait for "models": [...] response

# Run voice assistant
python run.py

# You'll see: "Ready! Listening for 'hey jarvis'..."

# Try it:
# 1. Say: "Hey jarvis"
# 2. Assistant: "Yes?"
# 3. You: "What's the capital of France?"
# 4. Assistant: "The capital of France is Paris"
```

---

## What Happens Next

### First Request (Cold Start)
1. You speak: "What's 2+2?"
2. Whisper transcribes locally
3. HTTP request sent to http://ollama.gke.dev
4. KEDA sees request → triggers pod scale-up
5. GCP provisions Spot node (2-4 minutes)
6. Ollama pod starts and loads model
7. Inference executes (< 1 second)
8. Piper converts response to audio
9. You hear the answer

### Subsequent Requests (Warm)
1. You speak: "What's 3+3?"
2. Whisper transcribes locally (< 500ms)
3. HTTP request to already-running pod (< 1 second)
4. Response synthesized locally (< 1 second)
5. Total latency: ~2-3 seconds

### After 5 Minutes Idle
Pod scales to 0 (KEDA managed) → Next request will be cold-start again

---

## Next: Where to Go from Here

1. **Setup & Run:** Follow INTEGRATION.md
2. **Configure Options:** See CONFIG_REFERENCE.md
3. **Troubleshoot:** Check QUICK_REFERENCE.md or COLD_START_GUIDE.md
4. **Customize:** Modify system prompt, wake word, models, devices in config.ini
5. **Monitor:** Watch cluster with `kubectl get pods -w`
6. **Cleanup:** Run `./scripts/cleanup.sh` when done (stops all costs)

---

## Additional Resources

**GitHub Repositories:**
- [gke-ollama-spot-ai](https://github.com/sancliffe/gke-ollama-spot-ai)
- [ollama-STT-TTS](https://github.com/sancliffe/ollama-STT-TTS)

**Official Documentation:**
- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [KEDA HTTP Add-on](https://keda.sh/docs/latest/scalers/http-add-on/)
- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper)
- [Piper TTS](https://github.com/rhasspy/piper)
- [GCP Spot VMs](https://cloud.google.com/compute/docs/instances/spot)

**Documentation in This Project:**
- `INTEGRATION.md` — Complete 5-step guide
- `CONFIG_REFERENCE.md` — All configuration options
- `COLD_START_GUIDE.md` — Cold start deep dive
- `QUICK_REFERENCE.md` — Quick lookup & troubleshooting

---

## Summary

You now have a complete, production-ready integration of two best-in-class open-source projects:

✅ **gke-ollama-spot-ai** — Cost-optimized cloud LLM backend ($5-10/month)
✅ **ollama-STT-TTS** — Local voice interface (Whisper + Piper)
✅ **Complete Documentation** — 4 guides covering every aspect
✅ **Automation Scripts** — Ready-to-run setup and configuration
✅ **Troubleshooting Guides** — Solutions for every common issue

Everything is in place. Follow INTEGRATION.md and you'll have a working voice assistant in < 1 hour. Good luck! 🚀
