#!/usr/bin/env python3

import argparse
from jinja2 import Environment, FileSystemLoader
import yaml
import os
import sys

VALID_BOOT_MODES = ['legacy', 'uefi']
DEFAULT_BOOT_MODE = 'legacy'
DEFAULT_BOOT_IMAGE = 'kali'
DEFAULT_RAM_SIZE = '2G'
DEFAULT_CPU_CORES = '2'
DEFAULT_CONTAINERS = 3  # Changed from 6 to 3 as a more reasonable default
DEFAULT_VOLUME_PREFIX = '.'  # Use current directory as default

def validate_boot_mode(mode):
    if mode not in VALID_BOOT_MODES:
        raise argparse.ArgumentTypeError(f"Boot mode must be one of: {', '.join(VALID_BOOT_MODES)}")
    return mode

def validate_container_count(count):
    if int(count) < 1:
        raise argparse.ArgumentTypeError("Number of containers must be at least 1")
    if int(count) > 100:
        raise argparse.ArgumentTypeError("Number of containers cannot exceed 100")
    return int(count)

def validate_volume_path(path):
    # Convert to absolute path if relative
    if path == '.':
        return path
    abs_path = os.path.abspath(path)
    
    # Just check if the path exists, don't try to create it
    if not os.path.exists(abs_path):
        raise argparse.ArgumentTypeError(f"Path does not exist: {abs_path}")
    
    return abs_path

def validate_file_path(path):
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        raise argparse.ArgumentTypeError(f"File does not exist: {abs_path}")
    return abs_path

def show_config_summary(args):
    print("\n🔧 Current Configuration:")
    print("------------------------")
    print(f"📦 Containers: {args.num_containers}")
    print(f"🏷️  Prefix: {args.prefix if args.prefix else args.boot_image}")
    print(f"💾 Boot Mode: {args.boot_mode}")
    print(f"🖼️  Boot Image: {args.boot_image}")
    print(f"🧠 RAM: {args.ram_size}")
    print(f"⚡ CPU Cores: {args.cpu_cores}")
    print(f"📂 Volume Path: {args.volume_prefix}")
    print("------------------------\n")

def check_output_directory(force: bool = False):
    output_dir = 'output'
    if force:
        os.makedirs(output_dir, exist_ok=True)
        return
    if os.path.exists(output_dir):
        files = [f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))]
        if files:
            print("⚠️  Output directory is not empty. Found files:")
            for file in files:
                print(f"   - {file}")
            response = input("\nDo you want to overwrite these files? [y/N]: ").lower()
            if response != 'y':
                print("❌ Operation cancelled")
                sys.exit(0)
            print("✅ Proceeding with overwrite\n")

def render_templates(args):
    # Check output directory
    check_output_directory(force=getattr(args, 'force', False))
    
    # Setup Jinja2 environment
    env = Environment(loader=FileSystemLoader('templates'))
    
    # Use custom prefix or boot image name
    container_prefix = args.prefix if args.prefix else args.boot_image
    
    # Load template variables
    template_vars = {
        'n': args.num_containers,
        'boot_mode': args.boot_mode,
        'boot_image': args.boot_image,
        'ram_size': args.ram_size,
        'cpu_cores': args.cpu_cores,
        'container_prefix': container_prefix,
        'volume_prefix': args.volume_prefix,
        # TLS Docker options (None if not provided)
        'docker_host': getattr(args, 'docker_host', None),
        'docker_ca': getattr(args, 'docker_ca', None),
        'docker_cert': getattr(args, 'docker_cert', None),
        'docker_key': getattr(args, 'docker_key', None),
    }
    
    # Ensure output directory exists
    os.makedirs('output', exist_ok=True)
    
    # Render docker-compose.yml
    docker_compose_template = env.get_template('docker-compose.j2')
    docker_compose_output = docker_compose_template.render(**template_vars)
    
    # Render Caddyfile
    caddyfile_template = env.get_template('Caddyfile.j2')
    caddyfile_output = caddyfile_template.render(**template_vars)
    
    # Write outputs
    with open('output/docker-compose.yml', 'w') as f:
        f.write(docker_compose_output)
    
    with open('output/Caddyfile', 'w') as f:
        f.write(caddyfile_output)
    
    print(f"✅ Generated configuration for {args.num_containers} QEMU containers")
    print(f"📁 Configuration files generated in 'output/' directory")

def main():
    parser = argparse.ArgumentParser(description='Render QEMU scale-to-zero configuration')
    parser.add_argument('-n', '--num-containers', type=validate_container_count, default=DEFAULT_CONTAINERS,
                      help=f'Number of QEMU containers (default: {DEFAULT_CONTAINERS}, max: 100)')
    parser.add_argument('--boot-mode', type=validate_boot_mode, default=DEFAULT_BOOT_MODE,
                      help=f'QEMU boot mode (default: {DEFAULT_BOOT_MODE}, valid: {", ".join(VALID_BOOT_MODES)})')
    parser.add_argument('--boot-image', default=DEFAULT_BOOT_IMAGE,
                      help=f'QEMU boot image (default: {DEFAULT_BOOT_IMAGE})')
    parser.add_argument('--ram-size', default=DEFAULT_RAM_SIZE,
                      help=f'RAM size per container (default: {DEFAULT_RAM_SIZE})')
    parser.add_argument('--cpu-cores', default=DEFAULT_CPU_CORES,
                      help=f'CPU cores per container (default: {DEFAULT_CPU_CORES})')
    parser.add_argument('--prefix', default=None,
                      help='Custom container name prefix (default: boot image name)')
    parser.add_argument('--volume-prefix', type=validate_volume_path, default=DEFAULT_VOLUME_PREFIX,
                      help=f'Volume path prefix (default: {DEFAULT_VOLUME_PREFIX})')
    # TLS / remote Docker options
    parser.add_argument('--docker-host', default=None,
                      help='Remote Docker host, e.g. tcp://host:2376 (enables TLS config in compose if set)')
    parser.add_argument('--docker-ca', type=validate_file_path, default=None,
                      help='Path to Docker TLS CA certificate (ca.pem)')
    parser.add_argument('--docker-cert', type=validate_file_path, default=None,
                      help='Path to Docker TLS client certificate (cert.pem)')
    parser.add_argument('--docker-key', type=validate_file_path, default=None,
                      help='Path to Docker TLS client key (key.pem)')
    parser.add_argument('--force', action='store_true', help='Overwrite files in output/ without confirmation')
    
    args = parser.parse_args()
    show_config_summary(args)
    render_templates(args)

if __name__ == '__main__':
    main()