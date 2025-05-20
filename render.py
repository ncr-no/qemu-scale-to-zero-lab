#!/usr/bin/env python3

import argparse
from jinja2 import Environment, FileSystemLoader
import yaml
import os

VALID_BOOT_MODES = ['legacy', 'uefi']
DEFAULT_BOOT_MODE = 'legacy'
DEFAULT_BOOT_IMAGE = 'kali'
DEFAULT_RAM_SIZE = '2G'
DEFAULT_CPU_CORES = '2'

def validate_boot_mode(mode):
    if mode not in VALID_BOOT_MODES:
        raise argparse.ArgumentTypeError(f"Boot mode must be one of: {', '.join(VALID_BOOT_MODES)}")
    return mode

def render_templates(args):
    # Setup Jinja2 environment
    env = Environment(loader=FileSystemLoader('.'))
    
    # Use custom prefix or boot image name
    container_prefix = args.prefix if args.prefix else args.boot_image
    
    # Load template variables
    template_vars = {
        'n': args.num_containers,
        'boot_mode': args.boot_mode,
        'boot_image': args.boot_image,
        'ram_size': args.ram_size,
        'cpu_cores': args.cpu_cores,
        'container_prefix': container_prefix
    }
    
    # Render docker-compose.yml
    docker_compose_template = env.get_template('docker-compose.j2')
    docker_compose_output = docker_compose_template.render(**template_vars)
    
    # Render Caddyfile
    caddyfile_template = env.get_template('Caddyfile.j2')
    caddyfile_output = caddyfile_template.render(**template_vars)
    
    # Write outputs
    with open('docker-compose.yml', 'w') as f:
        f.write(docker_compose_output)
    
    with open('Caddyfile', 'w') as f:
        f.write(caddyfile_output)
    
    print(f"Generated configuration for {args.num_containers} QEMU containers")
    print(f"Container prefix: {container_prefix}")
    print(f"Boot mode: {args.boot_mode}")
    print(f"Boot image: {args.boot_image}")
    print(f"RAM size: {args.ram_size}")
    print(f"CPU cores: {args.cpu_cores}")

def main():
    parser = argparse.ArgumentParser(description='Render QEMU scale-to-zero configuration')
    parser.add_argument('-n', '--num-containers', type=int, default=6,
                      help='Number of QEMU containers (default: 6)')
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
    
    args = parser.parse_args()
    render_templates(args)

if __name__ == '__main__':
    main() 