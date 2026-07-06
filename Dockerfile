FROM odoo:18.0

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libharfbuzz-subset0 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
    && python3 -m pip install --no-cache-dir --break-system-packages "weasyprint==66.0" \
    && rm -rf /var/lib/apt/lists/*

USER odoo
