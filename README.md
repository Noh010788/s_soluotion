# S Solution Odoo 18 Custom Addons

This repository contains only the custom Odoo 18 addons for S Solution.

It does not contain:

- Odoo core source
- Odoo config files
- Database dumps
- Filestore data
- SSH keys
- Passwords or credentials

## Branch Workflow

- `dev`: staging branch used on the local staging server.
- `main`: production branch used on the Google Cloud VM.

Recommended flow:

1. Make changes on `dev`.
2. Test on the local staging server.
3. Merge `dev` into `main` after testing.
4. Deploy `main` to Google Cloud production.

## Repository Structure

```text
web/
custom_addon/
scripts/
```

These folders map to the Odoo server paths:

```text
web/          -> /opt/odoo/custom-addons/web
custom_addon/ -> /opt/odoo/odoo18/custom_addon
```

## Staging Server

The local machine is the staging server.

Deploy `dev` to local staging:

```bash
cd /home/odoo18/Desktop/s_soluotion
git checkout dev
git pull origin dev
bash scripts/deploy_staging.sh
```

## Production Server

Google Cloud production server:

```text
35.240.218.251
```

Deploy `main` to production:

```bash
cd /home/odoo18/Desktop/s_soluotion
git checkout main
git pull origin main
bash scripts/deploy_production.sh
```

## Useful Odoo Commands

Check local staging:

```bash
sudo systemctl status odoo18 --no-pager
curl -I http://127.0.0.1:8069/web/login
```

Check production:

```bash
ssh -i /home/odoo18/.ssh/odoo18_gcp_migration souphanith_kolaogroup_com@35.240.218.251 'systemctl status odoo18 --no-pager'
curl -I http://35.240.218.251/web/login
```

## Notes

The `web_responsive` addon was patched to remove an outdated XPath targeting:

```xml
//t[@t-if='env.isSmall']
```

That XPath caused a blank white page after login on the Google Cloud production VM.

