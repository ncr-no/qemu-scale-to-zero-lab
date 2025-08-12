import os
import shutil
import yaml
from types import SimpleNamespace
from render import render_templates


def test_kali_uses_tmpfs_named_volumes(tmp_path):
    # Ensure isolated output and non-interactive overwrite
    args = SimpleNamespace(
        num_containers=2,
        boot_mode='legacy',
        boot_image='kali',
        ram_size='2G',
        cpu_cores='2',
        prefix=None,
        volume_prefix='.',
        docker_host=None,
        docker_ca=None,
        docker_cert=None,
        docker_key=None,
        force=True,
    )

    try:
        render_templates(args)
        compose_path = os.path.join('output', 'docker-compose.yml')
        assert os.path.exists(compose_path)

        with open(compose_path, 'r') as f:
            data = yaml.safe_load(f)

        services = data['services']
        # Verify service volume mounts use named volumes rather than host bind
        s1 = services['kali_1']
        s2 = services['kali_2']
        for svc, name in [(s1, 'kali_1'), (s2, 'kali_2')]:
            vols = svc.get('volumes', [])
            assert any(v == f"{name}:/storage:rw" for v in vols), f"Service {name} should mount named volume"
            assert not any(':/storage:rw' in v and v.startswith('.') for v in vols), "Should not use host bind for kali"

        # Verify top-level volumes define tmpfs with 50g limit for each
        vols_root = data.get('volumes', {})
        for name in ['kali_1', 'kali_2']:
            assert name in vols_root, f"Missing top-level volume {name}"
            vol_def = vols_root[name]
            assert vol_def.get('driver') == 'local'
            driver_opts = vol_def.get('driver_opts', {})
            assert driver_opts.get('type') == 'tmpfs'
            assert driver_opts.get('device') == 'tmpfs'
            assert driver_opts.get('o') == 'size=50g'
    finally:
        if os.path.isdir('output'):
            shutil.rmtree('output') 