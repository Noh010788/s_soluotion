# Monitoring Stack

This folder contains the local monitoring setup for the Odoo Docker project.

## Services

```text
Grafana     http://localhost:3000
Prometheus  http://localhost:9090
cAdvisor    http://localhost:8080
Blackbox    http://localhost:9115
```

Default Grafana login:

```text
Username: admin
Password: admin
```

## Start

Run from the project root:

```powershell
docker compose -p s_soluotion_git -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

## Stop

```powershell
docker compose -p s_soluotion_git -f docker-compose.yml -f docker-compose.monitoring.yml down
```

## Check

```powershell
docker ps
```

## Notes

- Grafana uses Prometheus as the default data source.
- cAdvisor monitors Docker container metrics.
- Blackbox exporter checks whether Odoo responds on `/web/login`.
- For full Windows host metrics, add Windows exporter later.
