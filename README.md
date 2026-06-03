# Ollama Cloud Voice Assistant

A hybrid AI architecture that pairs a highly responsive local speech-to-text/text-to-speech (STT/TTS) client with a cost-optimized, scale-to-zero LLM backend running on Google Kubernetes Engine (GKE) Autopilot.

This project bridges the gap between running heavy LLMs locally and paying for always-on cloud endpoints. By leveraging KEDA (Kubernetes Event-driven Autoscaling) and GCP Spot nodes, the heavy lifting of LLM inference is offloaded to the cloud for fractions of a cent, while maintaining a snappy local voice interface.

---

## Architecture Overview

This monorepo integrates two primary components:

1. **`backend/`**: A GKE Autopilot infrastructure deployment. It utilizes Spot pods to run Ollama and scales to zero using the KEDA HTTP Add-on when idle. 
2. **`frontend/`**: A lightweight local Python client utilizing ONNX models for fast, local voice recognition and synthesis.
3. **`bridge/`**: Automation scripts to seamlessly link the local frontend to the dynamic GKE backend.

## Prerequisites

* Google Cloud Platform (GCP) account with billing enabled.
* `gcloud` CLI installed and authenticated.
* `kubectl` configured.
* A Linux workstation (tested on Ubuntu 26.04 and Fedora) for local audio device management.
* Python 3.10+ and standard build tools.

---

## Repository Structure

```text
ollama-cloud-voice-assistant/
├── backend/                    # GKE cluster setup, KEDA manifests, and Ollama deployments
├── frontend/                   # Local Python voice assistant, ONNX models, and audio tools
└── bridge/                     # Integration scripts (connect-assistant.sh)
```

## Deployment Guide

### Phase 1: Cloud Backend Setup

Navigate to the `backend/` directory to spin up the GKE infrastructure.

**Provision the Cluster:**
Run the setup script to deploy the GKE Autopilot cluster and configure the necessary namespaces.

```bash
cd backend/scripts
./setup-cluster.sh
```

**Deploy KEDA & Ollama:**
Apply the Kubernetes manifests to deploy the Ollama workloads and the KEDA HTTP interceptor.

```bash
cd ../k8s
kubectl apply -f storage.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f keda-autoscaler.yaml
```

**Seed the Model:**
Initialize the persistent volume with your LLM of choice (e.g., `llama3` or `gemma2:2b`).

```bash
cd ../scripts
./seed-initial-model.sh
```

### Phase 2: The Integration Bridge

Once the backend is healthy, navigate to the `bridge/` directory. This script extracts the dynamic KEDA LoadBalancer IP from your GKE cluster, maps it to `ollama.gke.dev` in your local `/etc/hosts`, and updates the frontend configuration.

```bash
cd ../../bridge
./connect-assistant.sh
```

*Note: This script requires `sudo` access to modify your local hosts file.*

### Phase 3: Local Frontend Execution

With the cloud backend running and the DNS bridge established, start the local voice assistant.

**Install Dependencies:**

```bash
cd ../frontend
pip install -r requirements.txt
```

**Run the Assistant:**

```bash
python main.py
```

## Handling Cold Starts

To maximize cost efficiency, the GKE backend is designed to scale to 0 pods when idle.

**Cold Start Latency:** If the cluster is scaled down, your initial voice prompt will trigger KEDA to provision a new Spot node. This process takes approximately 2-4 minutes. Local HTTP timeouts in `config.ini` are adjusted to accommodate this initial delay. Once the node is warm, subsequent requests execute in milliseconds.

To manually pre-warm the cluster before interacting with the voice assistant, you can issue a simple curl command:

```bash
curl http://ollama.gke.dev/api/tags
```

## Documentation

For more detailed information, please refer to our comprehensive guides:
* [Integration Guide](docs/INTEGRATION.md): Complete step-by-step setup and architecture deep dive.
* [Quick Reference](docs/QUICK_REFERENCE.md): Cheat sheet for commands, config patterns, and latency.
* [Configuration Reference](docs/CONFIG_REFERENCE.md): All `config.ini` options explained.
* [Cold Start Guide](docs/COLD_START_GUIDE.md): Deep dive into latency management, pre-warming, and cost tradeoffs.

## License

MIT License. See LICENSE for details.
