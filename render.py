#!/usr/bin/env python3

import argparse
from jinja2 import Environment, FileSystemLoader
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

def validate_tls_config(args):
    """Validate TLS configuration when using remote Docker host"""
    if args.docker_host and not all([args.docker_ca, args.docker_cert, args.docker_key]):
        raise argparse.ArgumentTypeError(
            "When specifying --docker-host, all TLS certificates (--docker-ca, --docker-cert, --docker-key) must be provided"
        )

def get_user_input():
    """Get configuration from user input"""
    print("🚀 QEMU Scale-to-Zero Configuration Generator")
    print("=" * 50)
    
    # Ask user preference
    print("Choose configuration mode:")
    print("1. Use defaults (quick setup)")
    print("2. Customize all settings")
    
    while True:
        choice = input("\nEnter your choice (1 or 2): ").strip()
        if choice == "1":
            print("\n✅ Using default configuration...")
            return argparse.Namespace(
                num_containers=DEFAULT_CONTAINERS,
                boot_mode=DEFAULT_BOOT_MODE,
                boot_image=DEFAULT_BOOT_IMAGE,
                ram_size=DEFAULT_RAM_SIZE,
                cpu_cores=DEFAULT_CPU_CORES,
                prefix=None,
                volume_prefix=DEFAULT_VOLUME_PREFIX,
                docker_host="tcp://localhost:2376",
                docker_ca="/etc/certs/ca.pem",
                docker_cert="/etc/certs/cert.pem",
                docker_key="/etc/certs/key.pem",
                force=False
            )
        elif choice == "2":
            print("\n🔧 Custom configuration mode...")
            break
        else:
            print("❌ Please enter 1 or 2")
    
    # Number of containers
    while True:
        try:
            num_containers = input(f"Number of containers (default: {DEFAULT_CONTAINERS}): ").strip()
            if not num_containers:
                num_containers = DEFAULT_CONTAINERS
            else:
                num_containers = validate_container_count(num_containers)
            break
        except argparse.ArgumentTypeError as e:
            print(f"❌ {e}")
    
    # Boot mode
    while True:
        boot_mode = input(f"Boot mode (default: {DEFAULT_BOOT_MODE}, options: {', '.join(VALID_BOOT_MODES)}): ").strip()
        if not boot_mode:
            boot_mode = DEFAULT_BOOT_MODE
        else:
            try:
                boot_mode = validate_boot_mode(boot_mode)
                break
            except argparse.ArgumentTypeError as e:
                print(f"❌ {e}")
    
    # Boot image
    boot_image = input(f"Boot image (default: {DEFAULT_BOOT_IMAGE}): ").strip()
    if not boot_image:
        boot_image = DEFAULT_BOOT_IMAGE
    
    # RAM size
    ram_size = input(f"RAM size per container (default: {DEFAULT_RAM_SIZE}): ").strip()
    if not ram_size:
        ram_size = DEFAULT_RAM_SIZE
    
    # CPU cores
    cpu_cores = input(f"CPU cores per container (default: {DEFAULT_CPU_CORES}): ").strip()
    if not cpu_cores:
        cpu_cores = DEFAULT_CPU_CORES
    
    # Custom prefix
    prefix = input("Custom container name prefix (default: boot image name): ").strip()
    if not prefix:
        prefix = None
    
    # Volume path
    while True:
        volume_prefix = input(f"Volume path prefix (default: {DEFAULT_VOLUME_PREFIX}): ").strip()
        if not volume_prefix:
            volume_prefix = DEFAULT_VOLUME_PREFIX
        else:
            try:
                volume_prefix = validate_volume_path(volume_prefix)
                break
            except argparse.ArgumentTypeError as e:
                print(f"❌ {e}")
    
    # Docker configuration
    print("\n🐳 Docker Configuration:")
    docker_host = input("Remote Docker host (e.g., tcp://host:2376) or press Enter for local: ").strip()
    if not docker_host:
        docker_host = None
        docker_ca = None
        docker_cert = None
        docker_key = None
    else:
        while True:
            docker_ca = input("Path to Docker TLS CA certificate (ca.pem): ").strip()
            if not docker_ca:
                print("❌ CA certificate is required for remote Docker")
                continue
            try:
                break
            except argparse.ArgumentTypeError as e:
                print(f"❌ {e}")
        
        while True:
            docker_cert = input("Path to Docker TLS client certificate (cert.pem): ").strip()
            if not docker_cert:
                print("❌ Client certificate is required for remote Docker")
                continue
            try:
                break
            except argparse.ArgumentTypeError as e:
                print(f"❌ {e}")
        
        while True:
            docker_key = input("Path to Docker TLS client key (key.pem): ").strip()
            if not docker_key:
                print("❌ Client key is required for remote Docker")
                continue
            try:
                break
            except argparse.ArgumentTypeError as e:
                print(f"❌ {e}")
    
    # Force overwrite
    force = input("\nForce overwrite output files? [y/N]: ").strip().lower() == 'y'
    
    return argparse.Namespace(
        num_containers=num_containers,
        boot_mode=boot_mode,
        boot_image=boot_image,
        ram_size=ram_size,
        cpu_cores=cpu_cores,
        prefix=prefix,
        volume_prefix=volume_prefix,
        docker_host=docker_host,
        docker_ca=docker_ca,
        docker_cert=docker_cert,
        docker_key=docker_key,
        force=force
    )

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
    
    # TLS Docker configuration
    if args.docker_host:
        print(f"🐳 Docker Host: {args.docker_host}")
        print(f"🔐 TLS CA: {args.docker_ca}")
        print(f"🔑 TLS Cert: {args.docker_cert}")
        print(f"🔑 TLS Key: {args.docker_key}")
    else:
        print("🐳 Docker: Local (no TLS)")
    
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
                      help='Remote Docker host, e.g. tcp://host:2376 or tcp://192.168.1.100:2376')
    parser.add_argument('--docker-ca', type=validate_file_path, default=None,
                      help='Path to Docker TLS CA certificate file (e.g., /path/to/ca.pem)')
    parser.add_argument('--docker-cert', type=validate_file_path, default=None,
                      help='Path to Docker TLS client certificate file (e.g., /path/to/cert.pem)')
    parser.add_argument('--docker-key', type=validate_file_path, default=None,
                      help='Path to Docker TLS client key file (e.g., /path/to/key.pem)')
    parser.add_argument('--force', action='store_true', help='Overwrite files in output/ without confirmation')
    parser.add_argument('--non-interactive', action='store_true', help='Run with defaults without prompting')
    
    args = parser.parse_args()
    
    # If no arguments provided or non-interactive flag not set, run interactively
    if len(sys.argv) == 1 or not args.non_interactive:
        args = get_user_input()
    
    # Validate TLS configuration
    try:
        validate_tls_config(args)
    except argparse.ArgumentTypeError as e:
        parser.error(str(e))
    
    show_config_summary(args)
    render_templates(args)

if __name__ == '__main__':
    main()