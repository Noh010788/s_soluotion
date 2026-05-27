#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Deploying dev branch to local staging..."
cd "${REPO_DIR}"

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "${CURRENT_BRANCH}" != "dev" ]]; then
  echo "Refusing to deploy staging from branch '${CURRENT_BRANCH}'. Checkout dev first."
  exit 1
fi

sudo rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  "${REPO_DIR}/web/" /opt/odoo/custom-addons/web/

sudo rsync -a --delete --exclude='__pycache__' --exclude='*.pyc' \
  "${REPO_DIR}/custom_addon/" /opt/odoo/odoo18/custom_addon/

sudo chown -R odoo18:odoo18 /opt/odoo/custom-addons/web /opt/odoo/odoo18/custom_addon
sudo systemctl restart odoo18

echo "Staging deploy complete."
sudo systemctl status odoo18 --no-pager

