# GKE + Local Voice Assistant Integration Guide

This guide walks you through integrating the **`ollama-STT-TTS`** lightweight voice assistant with the **`gke-ollama-spot-ai`** cost-optimized LLM backend running on Google Kubernetes Engine.

## Architecture Overview

- **Remote "Brain"** ([`gke-ollama-spot-ai`](https://github.com/sancliffe/gke-ollama-spot-ai)): Ollama on GKE Autopilot with KEDA HTTP autoscaling and Spot nodes (~$5-10/month)
- **Local "Ears & Mouth"** ([`ollama-STT-TTS`](https://github.com/sancliffe/ollama-STT-TTS)): Python voice assistant with Whisper (STT), Piper (TTS), and openwakeword detection
- **Communication**: HTTP bridge via KEDA HTTP Add-on interceptor proxy (no code changes needed)

---

## Step 1: Deploy the GKE Backend and Seed the Model

### 1.1 Clone and Deploy the `gke-ollama-spot-ai` Backend

```bash
# Clone the GKE backend repository
git clone https://github.com/sancliffe/gke-ollama-spot-ai.git
cd gke-ollama-spot-ai

# Provision GKE cluster (5-10 minutes)
./scripts/setup-cluster.sh
```

This creates:
- GKE Autopilot cluster with Spot node pool
- Cluster name: `ai-spot-cluster`
- Region: `us-central1` (or `us-east1` if quota exhausted)

### 1.2 Install KEDA Core and HTTP Add-on (2-3 minutes)

```bash
# Install KEDA core with server-side apply (prevents annotation size errors)
kubectl apply -f https://github.com/kedacore/keda/releases/download/v2.13.0/keda-2.13.0.yaml --server-side

# Install KEDA HTTP Add-on via Helm (recommended)
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install http-add-on kedacore/keda-add-ons-http --namespace keda --create-namespace

# Wait for KEDA to be ready
kubectl wait -n keda --for=condition=ready pod -l app.kubernetes.io/name=keda-operator --timeout=120s
kubectl wait -n keda --for=condition=ready pod -l app.kubernetes.io/name=keda-http-add-on --timeout=120s
```

### 1.3 Deploy Ollama Stack (1-2 minutes)

```bash
# Apply all Kubernetes manifests
kubectl apply -f k8s/

# What gets deployed:
# - ollama-gpu Deployment (2 CPUs, 4GB RAM per pod, max 2 replicas)
# - ollama-service ClusterIP Service (internal only)
# - ollama-storage PersistentVolumeClaim (50GB)
# - ollama-http-scaler HTTPScaledObject (KEDA traffic monitoring)
```

### 1.4 Critical: Match Model Versions

The `ollama-STT-TTS` default model is **`llama3`** (7GB).  
The `gke-ollama-spot-ai` seed script defaults to **`gemma2:2b`** (2GB, faster, cheaper).

**Choose one approach:**

**Option A (Recommended for cost & speed):** Update seed script to use `gemma2:2b`
```bash
# Edit gke-ollama-spot-ai/scripts/seed-initial-model.sh
# Change: ollama pull llama3
# To:     ollama pull gemma2:2b
```

Then update your local config to match:
```bash
# You'll do this in Step 3
```

**Option B:** Keep both defaults (llama3 in both places)
```bash
# Keep the seed script as-is (pulls llama3)
# ollama-STT-TTS config.ini already defaults to llama3
```

**Option C:** Use a different model entirely
```bash
# Update seed script to any Ollama model: mistral, neural-chat, openchat, etc.
```

### 1.5 Seed the Model (5-10 minutes, happens once)

Run the seeding script (from gke-ollama-spot-ai root):

```bash
./scripts/seed-initial-model.sh
```

This:
- Sets deployment to 1 replica (disables KEDA during seeding)
- Waits for pod to be ready
- Pulls the model (e.g., gemma2:2b or llama3)
- Model persists in PersistentVolume across pod restarts

### 1.6 Retrieve Your KEDA IP Address

Get the external IP of the KEDA HTTP interceptor:

```bash
export KEDA_IP=$(kubectl get svc -n keda keda-http-add-on-interceptor-proxy -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "KEDA IP: $KEDA_IP"

# Verify it's accessible
curl http://$KEDA_IP/api/tags
# Should return JSON list of models
```

Save this IP—you'll need it in Step 2.

---

## Step 2: Configure Local DNS Routing

The KEDA HTTP Add-on routes traffic based on the hostname `ollama.gke.dev`. To securely reach it without modifying the Python API client, map this hostname locally.

### 2.1 Edit Your Hosts File

Add the following entry to your machine's hosts file:

**On Linux/macOS:**
```bash
sudo nano /etc/hosts
```

**On Windows:**
Open `C:\Windows\System32\drivers\etc\hosts` in a text editor as Administrator.

### 2.2 Add the Hostname Mapping

Add this line to your hosts file (replace `YOUR_KEDA_IP` with the actual IP from Step 1.5):

```plaintext
YOUR_KEDA_IP ollama.gke.dev
```

**Example:**
```plaintext
34.145.67.89 ollama.gke.dev
```

### 2.3 Verify the Mapping

Test the hostname resolution:

```bash
ping ollama.gke.dev
# Should resolve to your KEDA_IP
```

Test API connectivity:

```bash
curl http://ollama.gke.dev/api/tags
# Should return a JSON list of available models
```

---

## Step 3: Point the Voice Assistant to the Cloud

### 3.1 Clone the `ollama-STT-TTS` Voice Assistant

```bash
# Clone the voice assistant repository
git clone https://github.com/sancliffe/ollama-STT-TTS.git
cd ollama-STT-TTS

# Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install system dependencies (Linux only)
# On Debian/Ubuntu:
sudo apt-get update && sudo apt-get install -y portaudio19-dev ffmpeg

# On Fedora/RHEL:
sudo dnf install -y portaudio-devel gcc python3-devel ffmpeg pulseaudio-libs-devel
```

### 3.2 Install Python Dependencies

```bash
# From the ollama-STT-TTS directory with venv activated
pip install -r requirements.txt
```

### 3.3 List Available Audio Devices

Find your microphone and speaker device IDs:

```bash
python run.py --list-devices      # List input devices (microphone)
python run.py --list-output-devices  # List output devices (speaker)
```

Example output:
```
Input Devices:
0: USB Microphone
1: Built-in Microphone (Primary)

Output Devices:
0: Speaker
1: USB Audio
2: HDMI
```

### 3.4 Update config.ini for Cloud Backend

Edit the `config.ini` file and modify the `[Models]` section:

```ini
[Models]
# IMPORTANT: Model must match what's seeded in GKE backend
# If you seeded gemma2:2b in step 1.4:
ollama_model = gemma2:2b
# If you seeded llama3 or using Option B:
# ollama_model = llama3

# CRITICAL: Point to cloud backend instead of localhost
# Change from: http://localhost:11434
ollama_host = http://ollama.gke.dev
ollama_timeout = 120  # Increased for cold-start provisioning (2-4 min)

# Speech-to-text (runs locally on your machine)
whisper_model = base  # Options: tiny, base, small, medium, large

# Text-to-speech (runs locally on your machine)
piper_model = en_US-libritts_r

# Wake word detection (runs locally)
wakeword = hey_jarvis

[Audio]
# Device indices from --list-devices and --list-output-devices
device_index = 0  # Your microphone ID (from --list-devices)
piper_output_device_index = 0  # Your speaker ID (from --list-output-devices)
```

### 3.5 Verify Audio Configuration

Test with a quick run:

```bash
# This will list detected models and audio settings, then exit
python run.py --debug
# If you see errors about audio devices, re-run --list-devices and update config.ini
```

---

## Step 4: Account for KEDA "Cold Starts"

### The Problem

Because your GKE cluster uses KEDA to scale idle pods to zero:
- When the cluster is idle, there are **no running pods**
- The first HTTP request forces GKE to **provision a new Spot node**
- Node provisioning takes **2-4 minutes**
- Your HTTP request will likely **timeout locally** during this wait

### The Solution: Pre-warm the Cluster

**Before you start using the voice assistant** (especially first thing in the morning), manually warm up the cluster:

```bash
# Trigger pod scale-up
curl http://ollama.gke.dev/api/tags

# Wait 2-4 minutes for the node to provision and pod to start
# Once this command returns a JSON list, the cluster is ready
```

Alternatively, use a simple script to retry on failure:

```bash
#!/bin/bash
echo "Warming up GKE cluster..."
for i in {1..60}; do
  if curl -s http://ollama.gke.dev/api/tags > /dev/null 2>&1; then
    echo "Cluster is warm and ready!"
    exit 0
  fi
  echo "Attempt $i/60: Waiting for cluster to provision... ($(($i * 5)) seconds elapsed)"
  sleep 5
done

echo "Timeout: Cluster did not warm up in 300 seconds"
exit 1
```

### Understanding Timeout Configuration

The `config.ini` timeout settings are critical:

```ini
[Models]
ollama_timeout = 120     # Overall HTTP timeout (2 minutes)

[Timeouts]
http_request_timeout = 120  # Connection timeout
```

These values allow the voice assistant to wait through the cold-start provisioning window without timing out prematurely.

### Typical Latency Timeline

| Phase | Time | Notes |
|-------|------|-------|
| **Cold Start** | 2-4 min | Spot node provisioning + pod startup |
| **Warm Inference** | < 1 sec | Subsequent requests with running pod |
| **Idle Scaling** | 5 min | After 5 min of no requests, KEDA scales to 0 |

### First vs. Subsequent Requests

- **First request of the day**: 2-4 minutes (cold start)
- **Subsequent requests within 5 minutes**: < 1 second
- **After 5 minutes of inactivity**: Cold start again

This is the cost tradeoff: You pay nothing during idle periods but accept brief warm-up latency.

---

## Step 5: Run the Voice Assistant

### 5.1 Pre-warm the GKE Cluster

**Critical:** Cold-start provisioning takes 2-4 minutes. Before speaking to the assistant, warm up the cluster:

```bash
# Trigger cluster scale-up
curl http://ollama.gke.dev/api/tags

# Wait 2-4 minutes for Spot node provisioning
# Once the command returns a JSON list of models, the cluster is ready
```

Use this warming script to automate retries:

```bash
#!/bin/bash
echo "Pre-warming GKE cluster..."
for i in {1..60}; do
  if curl -s http://ollama.gke.dev/api/tags > /dev/null 2>&1; then
    echo "✓ Cluster is warm and ready!"
    exit 0
  fi
  echo "Attempt $i/60: Waiting for cluster... ($(($i * 5)) seconds elapsed)"
  sleep 5
done

echo "✗ Timeout: Cluster did not warm up"
exit 1
```

### 5.2 Start the Voice Assistant

From the `ollama-STT-TTS` directory with venv activated:

```bash
# Ensure venv is activated
source venv/bin/activate

# Start listening for wake word
python run.py
```

You'll see:
```
Ready! Listening for 'hey jarvis'...
```

### 5.3 How to Interact

1. **Say the wake word:** "Hey jarvis"
2. **Assistant responds:** "Yes?" and starts listening
3. **Speak your command:** "What's the capital of France?"
4. **Assistant responds:** Thinks, then speaks the answer aloud
5. **Repeat:** Back to listening for wake word

**Special commands:**
- Say **"goodbye"** or **"exit"** to stop the assistant
- Say **"new chat"** or **"reset chat"** to clear conversation history

### 5.4 Additional Command-Line Options

```bash
# List audio devices
python run.py --list-devices
python run.py --list-output-devices

# Use a different model
python run.py --ollama-model mistral

# Use a different Whisper model (STT)
python run.py --whisper-model small.en

# Enable debug logging
python run.py --debug

# Use different audio devices
python run.py --device-index 1 --piper-output-device-index 2

# Use custom system prompt
python run.py --system-prompt "You are a helpful pirate captain"
```

For a full list of options, see `config.ini` or run:
```bash
python run.py --help
```

---

## Troubleshooting

### Issue: "Connection refused to ollama.gke.dev"

**Solution:** Verify DNS mapping:
```bash
ping ollama.gke.dev
# Should resolve to your KEDA IP
```

If DNS fails, manually add to `/etc/hosts`:
```bash
export KEDA_IP=$(kubectl get svc -n keda keda-http-add-on-interceptor-proxy \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Edit /etc/hosts (Linux/macOS)
echo "$KEDA_IP ollama.gke.dev" | sudo tee -a /etc/hosts

# Or edit manually on Windows: C:\Windows\System32\drivers\etc\hosts
```

### Issue: "Model not found" or "API error"

**Solution:** Verify the model was seeded correctly:
```bash
# Check if pod is running
kubectl get pods -n default -l app=ollama

# Check pod logs
kubectl logs -n default -l app=ollama -f

# List models in container
kubectl exec -it $(kubectl get pods -n default -l app=ollama -o jsonpath="{.items[0].metadata.name}") -- ollama list

# Manually pull model if missing
kubectl exec -it $(kubectl get pods -n default -l app=ollama -o jsonpath="{.items[0].metadata.name}") -- ollama pull gemma2:2b
```

Also verify `ollama_model` in `config.ini` matches the seeded model.

### Issue: "Timeout waiting for LLM response" (on first request)

**This is normal behavior (cold start).** The cluster is provisioning a Spot node.

**Solution:**
1. Pre-warm the cluster BEFORE using the voice assistant:
   ```bash
   curl http://ollama.gke.dev/api/tags
   # Wait 2-4 minutes
   ```

2. Or increase timeout in `config.ini`:
   ```ini
   [Models]
   ollama_timeout = 180  # 3 minutes instead of 2
   ```

3. Subsequent requests will be < 1 second (once pod is running)

### Issue: "Audio device not found" or garbled audio

**Solution:** Find your correct audio devices:
```bash
python run.py --list-devices
python run.py --list-output-devices
```

Update `config.ini`:
```ini
[Audio]
device_index = 0  # Your actual microphone ID
piper_output_device_index = 0  # Your actual speaker ID
```

Or pass as command-line args:
```bash
python run.py --device-index 1 --piper-output-device-index 2
```

### Issue: "Wake word not detected" or too sensitive

**Solution:** Adjust wake word threshold in `config.ini`:
```ini
[Functionality]
wakeword_threshold = 0.5  # Lower = more sensitive, higher = less sensitive
vad_aggressiveness = 2    # 1-3: how aggressively silence is detected
```

Or via command line:
```bash
python run.py --wakeword-threshold 0.5 --vad-aggressiveness 2
```

### Issue: "KEDA IP not found" or kubectl errors

**Solution:** Verify GKE cluster and KEDA setup:
```bash
# Check cluster is running
kubectl get nodes

# Check KEDA pods
kubectl get pods -n keda

# Check KEDA HTTP Add-on specifically
kubectl get pods -n keda | grep http-add-on

# If missing, reinstall via Helm:
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install http-add-on kedacore/keda-add-ons-http \
  --namespace keda --create-namespace
```

### Issue: "Pod stuck in Pending" state

**Solution:** Check pod events:
```bash
kubectl describe pod -l app=ollama

# Common causes:
# 1. Insufficient Spot quota (try different region)
# 2. Spot VM preemption (wait and try again)
# 3. Node not provisioned yet (wait 5-10 minutes)
```

**Fix:** Restart the pod:
```bash
kubectl delete pod -l app=ollama
# Wait for new pod to start and image to pull
```

### Issue: "Model pull timeout" or "412 Precondition Failed"

**Solution:** The Ollama version may be outdated.

```bash
# Force restart deployment to pull latest image
kubectl rollout restart deployment/ollama-gpu

# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=ollama --timeout=300s

# Re-run seeding
cd gke-ollama-spot-ai
./scripts/seed-initial-model.sh
```

### Issue: Slow inference (responses take > 10 seconds)

**Solution:** Check resource usage and bottlenecks:

```bash
# Check CPU usage
kubectl top pod -l app=ollama

# Check if model is loaded
kubectl exec -it $(kubectl get pods -n default -l app=ollama -o jsonpath="{.items[0].metadata.name}") -- ollama list

# Check Ollama logs for errors
kubectl logs -l app=ollama -f
```

**Possible fixes:**
- Use smaller model (e.g., `gemma2:2b` instead of `llama3`)
- Increase pod CPU in `k8s/deployment.yaml`
- Switch to GPU version (see `gke-ollama-spot-ai` README)
- Check if pod is competing with other workloads

---

## Next Steps

**Quick checklist to get voice assistant running:**

1. ✅ Clone and deploy GKE backend
   ```bash
   git clone https://github.com/sancliffe/gke-ollama-spot-ai.git
   cd gke-ollama-spot-ai
   ./scripts/setup-cluster.sh
   # ... install KEDA and deploy Ollama ...
   ```

2. ✅ Get KEDA IP and update `/etc/hosts`
   ```bash
   export KEDA_IP=$(kubectl get svc -n keda keda-http-add-on-interceptor-proxy \
     -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
   echo "$KEDA_IP ollama.gke.dev" | sudo tee -a /etc/hosts
   ```

3. ✅ Clone and configure voice assistant
   ```bash
   git clone https://github.com/sancliffe/ollama-STT-TTS.git
   cd ollama-STT-TTS
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   python run.py --list-devices  # Find audio device IDs
   # Edit config.ini with correct ollama_host, model, and device IDs
   ```

4. ✅ Pre-warm the cluster
   ```bash
   curl http://ollama.gke.dev/api/tags
   # Wait 2-4 minutes
   ```

5. ✅ Start talking to the assistant
   ```bash
   python run.py
   # Say: "Hey jarvis"
   # Ask: "What's the capital of France?"
   ```

---

## Reference: Command-Line Quick Guide

```bash
# GKE backend operations
kubectl get pods -n default -l app=ollama                 # Check Ollama pod
kubectl get pods -n keda                                  # Check KEDA pods
kubectl logs -l app=ollama                                # View Ollama logs
kubectl top pod -l app=ollama                             # Check resource usage

# Voice assistant operations
python run.py                                             # Start assistant
python run.py --list-devices                              # List audio devices
python run.py --debug                                     # Enable debug mode
python run.py --ollama-model mistral                      # Use different model
python run.py --device-index 1                            # Use specific mic

# Cloud cluster warming
curl http://ollama.gke.dev/api/tags                       # Trigger scale-up
curl http://ollama.gke.dev/api/generate \                 # Test inference
  -d '{"model":"gemma2:2b","prompt":"Hello"}'

# Cleanup (when done to stop costs)
cd gke-ollama-spot-ai
./scripts/cleanup.sh                                      # Delete cluster & storage
```

---

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│ Local Workstation (ollama-STT-TTS)                                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─────────────────────────────────────────────────────┐             │
│  │ Python Voice Assistant (python run.py)              │             │
│  ├─────────────────────────────────────────────────────┤             │
│  │ ✓ Whisper STT (faster-whisper) [LOCAL, < 500ms]   │             │
│  │ ✓ Piper TTS (text-to-speech)   [LOCAL, < 1s]      │             │
│  │ ✓ openwakeword detection        [LOCAL, < 100ms]  │             │
│  │ ✓ webrtcvad (silence detection) [LOCAL]           │             │
│  │ ✗ LLM Inference (offloaded)     [REMOTE via HTTP] │             │
│  │                                                      │             │
│  │ Audio Input/Output: sounddevice library            │             │
│  └──────────────┬──────────────────────────────────────┘             │
│                 │                                                     │
│                 │ HTTP POST /api/generate                            │
│                 │ Headers: Host: ollama.gke.dev                      │
│                 │                                                     │
│                 ▼                                                     │
│  /etc/hosts: [KEDA_IP] ollama.gke.dev                               │
│  (Set by init script, no code changes needed)                       │
│                                                                        │
└────────────────┼───────────────────────────────────────────────────┬─┘
                 │                                                   │
         ┌───────┴────────────────────────────────────────────┐     │
         │         Internet / Corporate Network               │     │
         │         (TLS recommended for production)           │     │
         └───────┬────────────────────────────────────────────┘     │
                 │                                                   │
                 ▼                                                   │
┌──────────────────────────────────────────────────────────────────────┐
│ Google Cloud Platform (GKE Autopilot)                                │
│ Project: gke-ollama-spot-ai                                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─────────────────────────────────────────────────────┐             │
│  │ KEDA HTTP Add-on Interceptor                       │             │
│  │ Service: keda-http-add-on-interceptor-proxy        │             │
│  │ • Type: LoadBalancer                               │             │
│  │ • Port: 80                                         │             │
│  │ • Hostname Routing: ollama.gke.dev → Ollama pod   │             │
│  │ • Scaling Trigger: HTTP traffic                   │             │
│  └──────────────┬────────────────────────────────────┘             │
│                 │                                                   │
│                 ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐             │
│  │ Ollama Pod (Kubernetes Deployment)                 │             │
│  │ Managed by: HTTPScaledObject (KEDA)                │             │
│  ├─────────────────────────────────────────────────────┤             │
│  │ Resources: 2 CPUs, 4GB RAM per pod                │             │
│  │ Max Replicas: 2 (for load balancing)              │             │
│  │ Min Replicas: 0 (scales to zero when idle)       │             │
│  │ Model: gemma2:2b or llama3 (persistent)          │             │
│  │ Storage: 50GB PersistentVolumeClaim              │             │
│  │ Node Type: Spot VM (cost-optimized)              │             │
│  │ Availability: Scales up on first request         │             │
│  │ Latency: < 1 second (warm), 2-4 min (cold)       │             │
│  └─────────────────────────────────────────────────────┘             │
│                                                                        │
│  Cold Start Timeline:                                                 │
│    Step 1: Request arrives at KEDA proxy                            │
│    Step 2: KEDA detects traffic → scales from 0 to 1              │
│    Step 3: GCP provisions Spot node (2-4 min)                      │
│    Step 4: Ollama pod starts and loads model                       │
│    Step 5: Inference executes (< 1 sec)                            │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Voice Request Example

```
User:      "Hey Jarvis, what's the capital of France?"
              ↓
Whisper:   Transcribes audio → "What's the capital of France?"
              ↓
HTTP POST: Sends to http://ollama.gke.dev/api/generate
              ↓
KEDA:      Checks pod count
              │
              ├─ If running: Routes to Ollama pod immediately
              │
              └─ If zero: Provisions Spot node + starts pod (2-4 min wait)
              ↓
Ollama:    Generates response using gemma2:2b model
              ↓
HTTP:      Returns JSON with text response
              ↓
Piper TTS: Converts response to audio
              ↓
Speaker:   "The capital of France is Paris"
```

---

## Cost Breakdown

| Component | Cost | Notes |
|-----------|------|-------|
| **GKE Cluster Management** | $0/mo | Free Tier (Autopilot) |
| **Spot CPU (active)** | $0.02-0.04/hr | Only when pod running |
| **Persistent Storage** | ~$5/mo | 50GB disk (model cache) |
| **KEDA HTTP Add-on** | ~$0.05/mo | Minimal overhead |
| **Idle Time** | $0/mo | Pod scales to zero |
| **Monthly (1 hr/day)** | **~$5-10/mo** | Typical usage |
| **Monthly (idle only)** | **~$5/mo** | Storage only |

**Compared to alternatives:**
- Always-on GPU: ~$50-70/month
- Always-on CPU: ~$20-30/month
- KEDA auto-scale (this): ~$5-10/month

---

## Cost Optimization Tips

1. **Use `gemma2:2b`** instead of `llama3` (60% faster, 70% less memory, same quality)
2. **Embrace cold starts**: Idle time savings far exceed the 2-4 minute wait
3. **Pre-warm before peak usage**: Warm cluster at 8 AM before work starts (cron job)
4. **Monitor costs**: `gcloud billing accounts list`
5. **Set budget alerts**: GCP Console → Billing → Budgets & Alerts
6. **Clean up immediately**: Run `./scripts/cleanup.sh` when not in use (prevents orphaned costs)

---

## Further Reading

- **`gke-ollama-spot-ai` README**: Full Kubernetes deployment details
- **`ollama-STT-TTS` README**: Voice assistant configuration & troubleshooting
- [KEDA HTTP Add-on Documentation](https://keda.sh/docs/latest/scalers/http-add-on/)
- [GCP Spot VMs Documentation](https://cloud.google.com/compute/docs/instances/spot)
- [Ollama API Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [Faster Whisper Models](https://github.com/SYSTRAN/faster-whisper)
- [Piper TTS Documentation](https://github.com/rhasspy/piper)
