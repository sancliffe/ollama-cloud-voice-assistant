# GKE + Local Voice Assistant Integration Guide

This guide walks you through integrating your local lightweight voice assistant with a cost-optimized LLM backend running on Google Kubernetes Engine (GKE) Autopilot.

## Architecture Overview

- **Remote "Brain"**: `gke-ollama-spot-ai` project deployed on GKE Autopilot with KEDA autoscaling and Spot nodes
- **Local "Ears & Mouth"**: Lightweight Python voice assistant with ONNX-based STT/TTS models
- **Communication**: Secure HTTP bridge via KEDA HTTP Add-on interceptor proxy

---

## Step 1: Deploy the GKE Backend and Seed the Model

### 1.1 Deploy Your GKE Cluster

Navigate to your `gke-ollama-spot-ai` project and follow its 60-second deployment guide:

```bash
cd backend/scripts
./setup-cluster.sh
```

This script will:
- Create a GKE Autopilot cluster with Spot node pool
- Set up required namespaces
- Configure storage for model persistence

### 1.2 Apply Kubernetes Manifests

Deploy KEDA and Ollama to your cluster:

```bash
cd ../k8s
kubectl apply -f storage.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f keda-autoscaler.yaml
```

### 1.3 Critical: Match Model Versions

**Important:** Ensure your seeded model matches your local configuration.

- The `seed-initial-model.sh` script defaults to `gemma2:2b`
- Your local config defaults to `llama3`

**Choose one approach:**

**Option A (Recommended for cost):** Update seed script to use `gemma2:2b`
```bash
# Edit backend/scripts/seed-initial-model.sh
# Change: ollama pull llama3
# To:     ollama pull gemma2:2b
```

**Option B:** Use `llama3` in GKE (larger model, more resource-intensive)
```bash
# Edit backend/scripts/seed-initial-model.sh
# Keep: ollama pull llama3
```

### 1.4 Seed the Model

Run the initialization script (from your GKE project directory):

```bash
cd backend/scripts
./seed-initial-model.sh
```

This creates a persistent volume with your LLM, ensuring it survives pod restarts.

### 1.5 Retrieve Your KEDA IP Address

Get the external IP address of your KEDA interceptor:

```bash
export KEDA_IP=$(kubectl get svc -n keda keda-http-add-on-interceptor-proxy -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "Your KEDA IP: $KEDA_IP"
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

### 3.1 Update config.ini

Open the `frontend/config.ini` file and configure your local voice assistant:

```ini
[Models]
# The LLM model must match what you seeded in GKE (Step 1.3)
ollama_model = gemma2:2b
# OR if you chose llama3:
# ollama_model = llama3

# Point to your cloud backend instead of localhost
ollama_host = http://ollama.gke.dev
ollama_timeout = 240  # Increased timeout for cold start (see Step 4)

# ONNX-based local speech models (low-latency, runs locally)
stt_model = base  # Options: tiny, base, small, medium, large
tts_model = tts_models/en/ljspeech/glow-tts

[Audio]
# List available devices with: python list_audio_devices.py
input_device = 0    # Microphone device ID
output_device = 0   # Speaker device ID

[Timeouts]
# Adjusted for cloud latency + cold start provisioning
http_request_timeout = 240
speech_recognition_timeout = 30
synthesis_timeout = 30

[Logging]
log_level = INFO
log_file = assistant.log
```

### 3.2 Identify Your Audio Devices

If you're unsure about your audio device IDs:

```bash
cd frontend
python list_audio_devices.py
```

This will list all available microphones and speakers with their device IDs. Update `config.ini` with the correct IDs.

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

## Step 5: Automated Integration (Optional)

The `bridge/connect-assistant.sh` script automates Steps 2 and 3:

```bash
cd bridge
./connect-assistant.sh
```

This script will:
1. Fetch the KEDA IP from your cluster
2. Update `/etc/hosts` with `ollama.gke.dev` mapping
3. Update `frontend/config.ini` with the cloud host URL

**Note:** Requires `sudo` access to modify `/etc/hosts`.

---

## Troubleshooting

### Issue: "Could not find KEDA IP"
**Solution:** Ensure your GKE cluster is running and KEDA is deployed:
```bash
kubectl get svc -n keda keda-http-add-on-interceptor-proxy
```

### Issue: "Connection refused to ollama.gke.dev"
**Solution:** Check hostname resolution:
```bash
nslookup ollama.gke.dev
ping ollama.gke.dev
```
Update `/etc/hosts` if the IP has changed.

### Issue: "Timeout waiting for response from cloud LLM"
**Solution:** This is likely a cold start. Run the warm-up curl command:
```bash
curl http://ollama.gke.dev/api/tags
```
Wait 2-4 minutes for the Spot node to provision.

### Issue: "Model not found in cloud backend"
**Solution:** Verify the model was seeded correctly:
```bash
kubectl logs -n default -l app=ollama -f
```
Check that `seed-initial-model.sh` completed successfully and the model name matches `config.ini`.

### Issue: Audio device errors
**Solution:** List your audio devices:
```bash
python frontend/list_audio_devices.py
```
Update the device IDs in `config.ini` to match your system.

---

## Next Steps

1. ✅ Deploy GKE backend (Step 1)
2. ✅ Configure DNS routing (Step 2)
3. ✅ Update local config (Step 3)
4. ✅ Understand cold starts (Step 4)
5. ▶️ Install Python dependencies:
   ```bash
   cd frontend
   pip install -r requirements.txt
   ```
6. ▶️ Start the voice assistant:
   ```bash
   python main.py
   ```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Local Workstation                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────────────────────────────────┐              │
│  │ Python Voice Assistant (frontend/main.py)     │              │
│  ├───────────────────────────────────────────────┤              │
│  │ ✓ ONNX STT (whisper-base)      [Local]       │              │
│  │ ✓ ONNX TTS (Glow-TTS)          [Local]       │              │
│  │ ✗ LLM (offloaded to cloud)     [Remote]      │              │
│  └──────────────┬──────────────────────────────┘              │
│                 │                                                │
│                 │ HTTP Request                                   │
│                 │ POST http://ollama.gke.dev/api/generate      │
│                 │                                                │
│                 ▼                                                │
│  /etc/hosts: ollama.gke.dev → <KEDA_IP>                        │
│                                                                   │
└────────────────┼────────────────────────────────────────────────┘
                 │
         ┌───────┴────────┐
         │ Internet / VPN │
         └───────┬────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Google Cloud (GKE Autopilot)                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────┐             │
│  │ KEDA HTTP Add-on (keda-http-add-on-...)       │             │
│  │ • Port: 80 / 443                              │             │
│  │ • Hostname routing: ollama.gke.dev            │             │
│  └──────────────┬───────────────────────────────┘             │
│                 │                                                │
│                 ▼                                                │
│  ┌────────────────────────────────────────────────┐             │
│  │ Ollama Pod (Autoscaled via KEDA)              │             │
│  │ • Model: gemma2:2b or llama3                  │             │
│  │ • Storage: Persistent Volume                 │             │
│  │ • Node: Spot (cost-optimized)                │             │
│  │ • Scale: 0 → 1 pods (KEDA managed)          │             │
│  └────────────────────────────────────────────────┘             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Cost Optimization Tips

1. **Use `gemma2:2b`** instead of `llama3` for 60% lower inference costs
2. **Embrace cold starts**: The idle time cost savings far exceed the occasional 2-4 minute wait
3. **Monitor your cluster**: Use GCP Console to track Spot node usage and costs
4. **Set KEDA scale-down timeout**: Adjust to match your usage patterns

---

## Further Reading

- [KEDA HTTP Add-on Documentation](https://keda.sh/docs/latest/scalers/http-add-on/)
- [GCP Spot VMs Documentation](https://cloud.google.com/compute/docs/instances/spot)
- [Ollama API Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
