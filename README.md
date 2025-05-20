# QEMU Scale-to-Zero Lab

A scalable QEMU container deployment with scale-to-zero functionality using Sablier.

## Project Structure

```
├── render.py              # Template rendering script
├── Dockerfile            # Caddy with Sablier plugin
├── templates/            # Jinja2 templates
│   ├── docker-compose.j2 # Docker Compose template
│   └── Caddyfile.j2     # Caddy configuration template
└── output/              # Generated configuration files
    ├── docker-compose.yml
    └── Caddyfile
```

## Usage

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Generate configuration:
```bash
# Use defaults (6 containers, legacy boot, kali image, 2G RAM, 2 CPU cores)
python render.py

# Custom configuration
python render.py -n 10 --boot-image ubuntu --ram-size 4G --cpu-cores 4 --prefix vm
```

3. Deploy:
```bash
cd output
docker-compose up -d
```

## Configuration Options

- `-n, --num-containers`: Number of QEMU containers (default: 6)
- `--boot-mode`: QEMU boot mode (legacy/uefi, default: legacy)
- `--boot-image`: QEMU boot image (default: kali)
- `--ram-size`: RAM size per container (default: 2G)
- `--cpu-cores`: CPU cores per container (default: 2)
- `--prefix`: Custom container name prefix (default: boot image name)

## 🔧 Features

- ⚙️ Dynamically generated `docker-compose.yml` and `Caddyfile` for 1–100+ QEMU VMs
- 💻 Per-container terminal access via Sablier and web browser
- 🔁 Auto-scaling via sablier session lifecycle
- 🔐 Secure routing with Caddy reverse proxy
- 📦 Easy deployment with a single command

## 📁 Structure

- `render.py` — Python script to generate config files
- `templates/` — Jinja2 templates for Caddy and Docker
- `output/` — Auto-generated deployable configs

## 🚀 Usage

```bash
pip install -r requirements.txt
python generate.py
docker compose -f output/docker-compose.yml up -d
