#!/usr/bin/env bash
# deploy-vm.sh — Deploy BCD Portal to GCP VM (34.180.38.57)
#
# Prerequisites:
#   - gcloud CLI authenticated with Compute Engine access
#   - VM instance name and zone known
#   - Docker + Docker Compose installed on the VM
#
# Usage:
#   1. Find your VM instance name:
#      gcloud compute instances list --project=bcd-prototypes
#
#   2. SSH into the VM:
#      gcloud compute ssh <INSTANCE_NAME> --zone=<ZONE> --project=bcd-prototypes
#
#   3. On the VM, run these commands:

set -euo pipefail

echo "=== BCD Portal Deployment ==="

# 1. Clone or pull latest code
if [ -d "bcd_portal" ]; then
  echo "Updating existing repo..."
  cd bcd_portal
  git pull origin main
else
  echo "Cloning repo..."
  git clone https://github.com/tanuh-bcd/bcd_portal.git
  cd bcd_portal
fi

# 2. Copy credentials (must be done manually once)
if [ ! -f "gcp-service-account.json" ]; then
  echo ""
  echo "ERROR: gcp-service-account.json not found."
  echo "Copy it to $(pwd)/gcp-service-account.json before deploying."
  echo ""
  echo "From your local machine:"
  echo "  gcloud compute scp gcp-service-account.json <INSTANCE>:~/bcd_portal/ --zone=<ZONE> --project=bcd-prototypes"
  exit 1
fi

# 3. Create .env if not exists
if [ ! -f ".env" ]; then
  cat > .env << 'ENVEOF'
REACT_APP_WEBSITE_URL=https://www.tanuh.ai
REACT_APP_LINKEDIN_URL=https://www.linkedin.com/company/tanuh-aicoe/
REACT_APP_TWITTER_URL=https://x.com/TANUH_AI
REACT_APP_YOUTUBE_URL=https://www.youtube.com/@TANUH-AI

MYSQL_HOST=35.234.220.201
MYSQL_PORT=3306
MYSQL_DB=bcd_application2
MYSQL_USER=tanuh-bcd-portal@bcd-prototypes.iam.gserviceaccount.com
MYSQL_PASSWORD=
MYSQL_DRIVER=pymysql
MYSQL_QUERY=charset=utf8mb4
MYSQL_DB_QUESTIONNAIRE=bcd_questionnaire

CLOUD_SQL_CONNECTION_NAME=bcd-prototypes:asia-south1:tanuh-bcd-questionnaire-dev
USE_CLOUD_SQL_CONNECTOR=true

GCP_STORAGE_BUCKET=breast-cancer-image-dataset
GOOGLE_APPLICATION_CREDENTIALS=gcp-service-account.json
SECRET_KEY=9a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b

REACT_APP_MIXPANEL_TOKEN=

MYSQL_SSL_CA=
MYSQL_SSL_CERT=
MYSQL_SSL_KEY=
ENVEOF
  echo "Created .env"
fi

# 4. Build and start containers
echo "Building and starting containers..."
docker compose down 2>/dev/null || true
docker compose build --no-cache
docker compose up -d

# 5. Verify
echo ""
echo "Waiting for services to start..."
sleep 10

if curl -s http://localhost:8000/api/health | grep -q "healthy"; then
  echo "Backend: OK"
else
  echo "Backend: FAILED"
  docker compose logs backend --tail=20
fi

if curl -s http://localhost/ | grep -q "root"; then
  echo "Frontend: OK"
else
  echo "Frontend: FAILED"
  docker compose logs frontend --tail=20
fi

echo ""
echo "=== Deployment Complete ==="
echo "Access the portal at: http://34.180.38.57"
echo "Backend API at: http://34.180.38.57:8000"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f          # View logs"
echo "  docker compose restart           # Restart services"
echo "  docker compose down && docker compose up -d  # Full restart"
