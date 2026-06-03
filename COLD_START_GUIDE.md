# Cold Start Management Guide

## Understanding KEDA Scaling Behavior

Your voice assistant uses KEDA (Kubernetes Event-driven Autoscaling) to **scale Ollama pods to zero** when idle. This saves money but introduces "cold start" latency.

### Scaling Timeline

```
Initial Request (Cold)
├─ HTTP request arrives at KEDA proxy
├─ KEDA detects request → triggers scale-up
├─ GCP provisions Spot node (2-4 minutes)
│  └─ Node startup, Ollama pod launch, model loading
└─ LLM inference completes (< 1 second)
   └─ TOTAL: ~2-4 minutes

Subsequent Requests (Warm)
├─ Pod is running
├─ LLM inference executes (< 1 second)
└─ TOTAL: < 1 second

Idle Period (5 minutes)
├─ No requests for 5 minutes
├─ KEDA scales pod count to 0
└─ Next request will be cold again
```

### Cost Tradeoff

| Approach | Cost | Latency | Uptime |
|----------|------|---------|--------|
| **Always-on pod** | ~$50/month | 1 sec | 24/7 |
| **KEDA auto-scaling (default)** | ~$5/month | 2-4 min (cold) | On-demand |
| **Always-off (manual)** | ~$0/month | ∞ (wait for user to start) | Manual |

---

## Pre-warming the Cluster

### Method 1: Manual Warm-up (Recommended)

Before using your voice assistant, especially first thing in the morning:

```bash
# Trigger the cluster to scale up
curl http://ollama.gke.dev/api/tags

# Wait for response (2-4 minutes on cold start)
# Once successful, subsequent requests will be fast
```

The `/api/tags` endpoint is lightweight and fast to warm up the cluster.

### Method 2: Automated Warm-up Script

Create `warm-cluster.sh` to automatically handle cold-start retries:

```bash
#!/bin/bash

echo "Warming up GKE cluster..."
TIMEOUT=300  # 5 minutes
START_TIME=$(date +%s)

while true; do
  CURRENT_TIME=$(date +%s)
  ELAPSED=$((CURRENT_TIME - START_TIME))
  
  if curl -s -m 5 http://ollama.gke.dev/api/tags > /dev/null 2>&1; then
    echo "✓ Cluster is warm and ready! (${ELAPSED}s elapsed)"
    exit 0
  fi
  
  if [ $ELAPSED -gt $TIMEOUT ]; then
    echo "✗ Timeout: Cluster did not warm up in ${TIMEOUT}s"
    exit 1
  fi
  
  echo "  Warming up... (${ELAPSED}s elapsed) Retrying in 10 seconds..."
  sleep 10
done
```

**Usage:**
```bash
chmod +x warm-cluster.sh
./warm-cluster.sh
```

### Method 3: Cron Job for Periodic Pre-warming

Automatically warm up your cluster before peak usage times:

```bash
# Edit your crontab
crontab -e

# Add this line to warm up at 8 AM every weekday
0 8 * * 1-5 /path/to/warm-cluster.sh >> /tmp/warm-cluster.log 2>&1
```

---

## Handling Timeouts in Your Application

### Configuration Settings

Ensure your `config.ini` has appropriate timeouts:

```ini
[Models]
ollama_timeout = 240        # 4 minutes total timeout

[Timeouts]
http_request_timeout = 240  # 4 minutes HTTP timeout
```

### Python Client Implementation

When making requests to the cloud LLM, implement retry logic:

```python
import requests
import time

def call_ollama_with_retry(prompt, max_retries=3, timeout=120):
    """Call Ollama with exponential backoff retry on timeout."""
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "http://ollama.gke.dev/api/generate",
                json={"model": "gemma2:2b", "prompt": prompt},
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.Timeout:
            print(f"Attempt {attempt + 1}: Timeout (cold start in progress?)")
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 5  # Exponential backoff
                print(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
                
        except requests.ConnectionError:
            print(f"Attempt {attempt + 1}: Connection failed")
            if attempt < max_retries - 1:
                time.sleep(10)
            else:
                raise
```

---

## Monitoring Cold Starts

### Check if Cluster is Warm

```bash
# Fast check (no model loading)
curl -s http://ollama.gke.dev/api/tags | jq '.models'

# Detailed status (triggers pod startup if cold)
curl -s http://ollama.gke.dev/api/show -d '{"name":"gemma2:2b"}' | jq '.model'
```

### Watch Pod Status in Real-Time

```bash
# Watch Ollama pods
kubectl get pods -n default -l app=ollama -w

# Wait for pods to be ready after requesting
watch -n 1 'kubectl get pods -n default -l app=ollama'
```

### Check KEDA Scaler Status

```bash
# See KEDA metrics
kubectl get hpa -n keda -o wide

# View KEDA logs
kubectl logs -n keda -l app=keda-operator -f
```

---

## Cluster Status Dashboard

Create a simple monitoring script to check cluster health:

```bash
#!/bin/bash
# cluster-status.sh

echo "=== GKE Ollama Cluster Status ==="
echo

echo "1. KEDA Service:"
kubectl get svc -n keda keda-http-add-on-interceptor-proxy
echo

echo "2. Ollama Deployment:"
kubectl get deployment -n default -l app=ollama
echo

echo "3. Ollama Pods:"
kubectl get pods -n default -l app=ollama
echo

echo "4. Persistent Volume:"
kubectl get pv -l app=ollama
echo

echo "5. Quick Connectivity Test:"
if curl -s -m 5 http://ollama.gke.dev/api/tags > /dev/null; then
  echo "✓ Cluster is responding (WARM)"
else
  echo "✗ Cluster not responding yet (may be COLD - starting up...)"
fi
```

**Usage:**
```bash
chmod +x cluster-status.sh
./cluster-status.sh
```

---

## Troubleshooting Cold Start Issues

### Problem: "Connection timeout" on first request

**Expected behavior** — cold starts take 2-4 minutes. This is normal.

**Solution:**
1. Pre-warm the cluster before using voice commands
2. Increase timeout in `config.ini` to 180 seconds (3 minutes)
3. Implement retry logic in your Python code

### Problem: Cluster scales down too quickly

If your cluster scales to zero after only 1-2 minutes of inactivity:

```bash
# Check KEDA trigger metadata
kubectl get scaledobject -n default ollama-scaler -o yaml

# Look for the "cooldownPeriod" setting (default 5 minutes)
# If set too low, increase it in your KEDA configuration
```

### Problem: "Model not found" after cold start

The model might not have loaded completely. Wait a few more seconds and retry:

```bash
# Check model in container
kubectl exec -it deployment/ollama -c ollama -- ollama list

# If model isn't loaded, trigger seeding
kubectl exec -it deployment/ollama -c ollama -- ollama pull gemma2:2b
```

### Problem: Spot node provisioning fails

GCP occasionally runs out of Spot capacity. This will fail gracefully:

```bash
# Check if your cluster fell back to on-demand
kubectl get nodes --show-labels | grep cloud.google.com/gke-nodepool

# Check GCP Compute quota
gcloud compute project-info describe --project=$PROJECT_ID --format='value(quotas)'
```

---

## Best Practices

### ✅ DO:
- ✅ Pre-warm the cluster before important voice sessions
- ✅ Monitor pod status with `kubectl get pods -w`
- ✅ Set reasonable timeouts (120+ seconds)
- ✅ Implement retry logic in your voice assistant
- ✅ Use `gemma2:2b` for faster cold starts (2GB model)

### ❌ DON'T:
- ❌ Don't panic on first-request timeouts (it's normal)
- ❌ Don't set timeouts lower than 60 seconds (you'll hit cold starts)
- ❌ Don't use `llama3` if you need fast cold starts (7GB model)
- ❌ Don't run the cluster 24/7 (defeats the cost savings)
- ❌ Don't assume pods are always running (KEDA scales to zero)

---

## Further Reading

- [KEDA HTTP Add-on Autoscaling](https://keda.sh/docs/latest/scalers/http-add-on/)
- [GCP Spot VMs Cost Savings](https://cloud.google.com/compute/docs/instances/spot)
- [Kubernetes Event-driven Autoscaling](https://keda.sh/docs/)
