#!/bin/bash
# Bridge Script: Connect local voice assistant to GKE cloud backend
# This script automates DNS routing and configuration for seamless cloud integration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/../frontend"
HOSTS_FILE="/etc/hosts"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}GKE Cloud Voice Assistant Bridge Script${NC}"
echo -e "${GREEN}================================================${NC}"
echo

# Step 1: Verify kubectl and curl are available
echo -e "${YELLOW}[1/5]${NC} Checking required commands..."
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl not found. Please install kubectl.${NC}"
    exit 1
fi
if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl not found. Please install curl.${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Dependencies (kubectl, curl) are installed"
echo

# Step 2: Fetch KEDA IP
echo -e "${YELLOW}[2/5]${NC} Fetching KEDA Interceptor IP from GKE..."
KEDA_IP=$(kubectl get svc -n keda keda-http-add-on-interceptor-proxy -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)

if [ -z "$KEDA_IP" ]; then
    echo -e "${RED}Error: Could not find KEDA IP. Possible issues:${NC}"
    echo "  1. GKE cluster is not running"
    echo "  2. KEDA is not deployed (run kubectl apply -f k8s/keda-autoscaler.yaml)"
    echo "  3. LoadBalancer IP not assigned yet (wait 1-2 minutes)"
    echo
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "  kubectl get svc -n keda"
    echo "  kubectl get svc -n keda keda-http-add-on-interceptor-proxy"
    exit 1
fi

echo -e "${GREEN}✓${NC} Found KEDA backend at: $KEDA_IP"
echo

# Step 3: Test connectivity
echo -e "${YELLOW}[3/5]${NC} Testing connectivity to cloud backend..."
HTTP_CODE=$(timeout 10 curl -s -o /dev/null -w "%{http_code}" "http://${KEDA_IP}/api/tags" || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓${NC} Cloud backend is responding (cluster is WARM)"
elif [[ "$HTTP_CODE" =~ ^(503|502|404)$ ]]; then
    echo -e "${YELLOW}⚠${NC} Cloud backend is responding but may be cold (HTTP $HTTP_CODE - this is normal)"
else
    echo -e "${YELLOW}⚠${NC} Could not reach cloud backend yet (may still be starting up, HTTP $HTTP_CODE)"
    echo "    This is normal - KEDA will provision pods on first request"
fi
echo

# Step 4: Update /etc/hosts
echo -e "${YELLOW}[4/5]${NC} Updating /etc/hosts with DNS mapping..."
echo "    Mapping: $KEDA_IP ollama.gke.dev"

# Check if sudo is available
if ! sudo -n true 2>/dev/null; then
    echo -e "${YELLOW}⚠${NC} This script needs sudo access to modify /etc/hosts"
    echo "    You will be prompted for your password..."
fi

# Remove old entry if it exists
sudo sed -i.bak '/ollama.gke.dev/d' "$HOSTS_FILE"

# Add new entry
echo "$KEDA_IP ollama.gke.dev" | sudo tee -a "$HOSTS_FILE" > /dev/null

# Verify the entry
if grep -q "ollama.gke.dev" "$HOSTS_FILE"; then
    echo -e "${GREEN}✓${NC} DNS mapping added to $HOSTS_FILE"
else
    echo -e "${RED}Error: Failed to update $HOSTS_FILE${NC}"
    exit 1
fi
echo

# Step 5: Update config.ini
echo -e "${YELLOW}[5/5]${NC} Updating frontend configuration..."

if [ ! -f "$FRONTEND_DIR/config.ini" ]; then
    echo -e "${RED}Error: $FRONTEND_DIR/config.ini not found${NC}"
    exit 1
fi

# Update the ollama_host configuration
sed -i.bak 's|ollama_host = .*|ollama_host = http://ollama.gke.dev|g' "$FRONTEND_DIR/config.ini"

if grep -q "ollama_host = http://ollama.gke.dev" "$FRONTEND_DIR/config.ini"; then
    echo -e "${GREEN}✓${NC} Configuration updated successfully"
else
    echo -e "${RED}Error: Failed to update config.ini${NC}"
    exit 1
fi
echo

# Summary
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}✓ Integration Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo
echo "Your voice assistant is now configured to use the cloud backend:"
echo "  • Backend Host: http://ollama.gke.dev"
echo "  • KEDA IP: $KEDA_IP"
echo "  • Config File: $FRONTEND_DIR/config.ini"
echo
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Verify DNS resolution:"
echo "     ping ollama.gke.dev"
echo
echo "  2. Warm up the cluster (cold start takes 2-4 minutes):"
echo "     curl http://ollama.gke.dev/api/tags"
echo
echo "  3. Install Python dependencies:"
echo "     cd $FRONTEND_DIR"
echo "     pip install -r requirements.txt"
echo
echo "  4. Run the voice assistant:"
echo "     python main.py"
echo
echo -e "${YELLOW}Cold Start Warning:${NC}"
echo "  The first request to a cold cluster may take 2-4 minutes."
echo "  Pre-warm the cluster before important voice sessions."
echo "  See docs/COLD_START_GUIDE.md for details."
echo