# Quick Reference: Cloud Voice Assistant

## Essential Commands

### 1. Pre-warm GKE Cluster (Do this FIRST)
```bash
curl http://ollama.gke.dev/api/tags
# Wait 2-4 minutes on cold start, then subsequent requests are < 1 second
```

### 2. Run the Integration Bridge
```bash
cd bridge
./connect-assistant.sh
# Requires: GKE cluster running, KEDA deployed, kubectl configured
```

### 3. Start the Voice Assistant
```bash
cd frontend
pip install -r requirements.txt
python main.py
```

### 4. Find Audio Device IDs
```bash
cd frontend
python list_audio_devices.py
# Update input_device and output_device in config.ini
```

---

## Configuration Quick Reference

**File:** `frontend/config.ini`

| Setting | Default | Purpose |
|---------|---------|---------|
| `ollama_model` | `gemma2:2b` | LLM model (must match GKE seed) |
| `ollama_host` | `http://ollama.gke.dev` | Cloud backend URL |
| `ollama_timeout` | `240` | HTTP timeout (seconds) |
| `stt_model` | `base` | Speech-to-text model size |
| `input_device` | `0` | Microphone device ID |
| `output_device` | `0` | Speaker device ID |

---

## Troubleshooting Checklist

```bash
# 1. Check GKE cluster status
kubectl get nodes
kubectl get deployment -n default -l app=ollama

# 2. Check KEDA setup
kubectl get svc -n keda keda-http-add-on-interceptor-proxy

# 3. Verify DNS mapping
ping ollama.gke.dev
nslookup ollama.gke.dev

# 4. Test cloud connectivity
curl http://ollama.gke.dev/api/tags

# 5. Check local model list
curl http://ollama.gke.dev/api/tags | jq '.models'

# 6. View Ollama pod logs
kubectl logs -n default -l app=ollama -f

# 7. Watch pod scaling
kubectl get pods -n default -l app=ollama -w
```

---

## Model Versions

### Fast/Cost-Optimized (Recommended)
- **Model:** `gemma2:2b`
- **Size:** 2GB
- **Inference Speed:** Fast (~500ms)
- **Cost:** ~$0.003 per 1M tokens

### Balanced Quality
- **Model:** `llama2:7b`
- **Size:** 7GB
- **Inference Speed:** Medium (~2s)
- **Cost:** ~$0.010 per 1M tokens

### Best Quality
- **Model:** `llama3`
- **Size:** 7GB
- **Inference Speed:** Medium (~2s)
- **Cost:** ~$0.015 per 1M tokens

---

## Expected Latency

| Scenario | Latency | Notes |
|----------|---------|-------|
| **Cold start (first request)** | 2-4 min | GCP provisions Spot node |
| **Warm inference** | < 1 sec | Pod already running |
| **Speech recognition (local)** | < 500ms | ONNX model on your machine |
| **Speech synthesis (local)** | < 1 sec | Glow-TTS on your machine |
| **Total (warm)** | ~2-3 sec | STT + API + TTS |
| **Total (cold)** | 2-4 min | First request scales cluster |

---

## Cost Breakdown

Assuming `gemma2:2b` on GKE Autopilot with Spot nodes:

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| **GKE Autopilot** | ~$2 | Management fee + idle cluster |
| **Spot CPU (on-demand)** | ~$2-5 | Scales to 0, only pays when running |
| **Persistent Volume** | ~$0.50 | 10GB storage for model |
| **Data transfer (out)** | $0.12/GB | First 1GB free |
| **Total Estimated** | **~$5-10/month** | Highly variable by usage |

---

## Common Configuration Patterns

### Pattern 1: Maximum Cost Savings
```ini
[Models]
ollama_model = gemma2:2b
ollama_timeout = 240

[Timeouts]
http_request_timeout = 240

[Audio]
input_device = 0
output_device = 0
```

### Pattern 2: Balanced Speed & Cost
```ini
[Models]
ollama_model = llama2:7b
ollama_timeout = 240

[Audio]
input_device = 0
output_device = 0
```

### Pattern 3: Always Warm (Higher Cost)
Edit KEDA configuration to prevent scale-to-zero:
```bash
kubectl patch scaledobject ollama-scaler --type merge -p '{"spec":{"minReplicaCount":1}}'
```

---

## Environment Setup

### Prerequisites Check
```bash
# 1. Check kubectl
kubectl version

# 2. Check current context
kubectl config current-context

# 3. Check GKE cluster
gcloud container clusters list

# 4. Check authentication
gcloud auth list
```

### First-Time Setup
```bash
# 1. Deploy GKE cluster (from gke-ollama-spot-ai)
cd backend/scripts
./setup-cluster.sh

# 2. Deploy KEDA and Ollama
cd ../k8s
kubectl apply -f storage.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f keda-autoscaler.yaml

# 3. Seed the model
cd ../scripts
./seed-initial-model.sh

# 4. Run bridge script
cd ../../bridge
./connect-assistant.sh

# 5. Install local dependencies
cd ../frontend
pip install -r requirements.txt

# 6. Start voice assistant
python main.py
```

---

## Monitoring Dashboard Commands

```bash
# Real-time cluster status
watch -n 2 'kubectl get pods,svc,pvc -n default; echo "---"; kubectl get svc -n keda'

# Pod autoscaling activity
kubectl get hpa -n default -w

# Network activity
kubectl logs -n keda -l app=keda-operator -f

# Ollama-specific metrics
kubectl exec -it deployment/ollama -c ollama -- ollama list

# GKE node status
kubectl get nodes --show-labels
```

---

## Files & Directories

| Path | Purpose |
|------|---------|
| `INTEGRATION.md` | Complete step-by-step integration guide |
| `COLD_START_GUIDE.md` | Cold start management & optimization |
| `frontend/config.ini` | Voice assistant configuration |
| `frontend/main.py` | Voice assistant entry point |
| `bridge/connect-assistant.sh` | Automated bridge setup |
| `backend/k8s/` | Kubernetes manifests |
| `backend/scripts/` | GKE setup scripts |

---

## Debugging Tips

**Problem: "Connection refused"**
- Check: `ping ollama.gke.dev`
- Fix: Re-run `./connect-assistant.sh`

**Problem: "Timeout"**
- This is normal on first request (cold start)
- Pre-warm: `curl http://ollama.gke.dev/api/tags`
- Then wait 2-4 minutes

**Problem: "Model not found"**
- Check: `curl http://ollama.gke.dev/api/tags | jq '.models'`
- Fix: Update config.ini to match seeded model

**Problem: "Audio device errors"**
- List devices: `python frontend/list_audio_devices.py`
- Update: `input_device` and `output_device` in config.ini

---

## Further Resources

- **Full Integration Guide:** [INTEGRATION.md](./INTEGRATION.md)
- **Cold Start Management:** [COLD_START_GUIDE.md](./COLD_START_GUIDE.md)
- **Main README:** [README.md](./README.md)
- **KEDA Documentation:** https://keda.sh/
- **Ollama API Docs:** https://github.com/ollama/ollama/blob/main/docs/api.md
- **GCP Spot VMs:** https://cloud.google.com/compute/docs/instances/spot
