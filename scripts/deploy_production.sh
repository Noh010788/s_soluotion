#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROD_USER="souphanith_kolaogroup_com"
PROD_HOST="35.240.218.251"
SSH_KEY="/home/odoo18/.ssh/odoo18_gcp_migration"

echo "Deploying main branch to Google Cloud production..."
cd "${REPO_DIR}"

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "${CURRENT_BRANCH}" != "main" ]]; then
  echo "Refusing to deploy production from branch '${CURRENT_BRANCH}'. Checkout main first."
  exit 1
fi

rsync -az --delete -e "ssh -i ${SSH_KEY}" --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  "${REPO_DIR}/web/" "${PROD_USER}@${PROD_HOST}:/tmp/s_soluotion_web/"

rsync -az --delete -e "ssh -i ${SSH_KEY}" --exclude='__pycache__' --exclude='*.pyc' \
  "${REPO_DIR}/custom_addon/" "${PROD_USER}@${PROD_HOST}:/tmp/s_soluotion_custom_addon/"

ssh -i "${SSH_KEY}" "${PROD_USER}@${PROD_HOST}" '
  set -euo pipefail
  sudo rsync -a --delete --exclude=".git" --exclude="__pycache__" --exclude="*.pyc" /tmp/s_soluotion_web/ /opt/odoo/custom-addons/web/
  sudo rsync -a --delete --exclude="__pycache__" --exclude="*.pyc" /tmp/s_soluotion_custom_addon/ /opt/odoo/odoo18/custom_addon/
  sudo chown -R odoo18:odoo18 /opt/odoo/custom-addons/web /opt/odoo/odoo18/custom_addon
  sudo systemctl restart odoo18
  sleep 3
  systemctl is-active odoo18
'

echo "Production deploy complete."
curl -s -o /dev/null -w "production_http:%{http_code} time:%{time_total}\n" "http://${PROD_HOST}/web/login"

