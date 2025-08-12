import os
import tempfile
import shutil
import yaml
from types import SimpleNamespace
from render import render_templates


def test_render_compose_with_tls(tmp_path):
    # Prepare fake cert files
    ca = tmp_path / "ca.pem"
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    for p in (ca, cert, key):
        p.write_text("test")

    # Ensure output dir is isolated
    cwd = os.getcwd()
    try:
        # Run render in project root but with force to avoid prompt
        args = SimpleNamespace(
            num_containers=1,
            boot_mode='legacy',
            boot_image='kali',
            ram_size='2G',
            cpu_cores='2',
            prefix=None,
            volume_prefix='.',
            docker_host='tcp://docker.example.com:2376',
            docker_ca=str(ca),
            docker_cert=str(cert),
            docker_key=str(key),
            force=True,
        )
        render_templates(args)
        compose_path = os.path.join('output', 'docker-compose.yml')
        assert os.path.exists(compose_path)
        with open(compose_path, 'r') as f:
            data = yaml.safe_load(f)
        # Check sablier env and volumes
        sablier = data['services']['sablier']
        env = sablier.get('environment', {})
        assert env.get('DOCKER_HOST') == 'tcp://docker.example.com:2376'
        assert env.get('DOCKER_TLS_VERIFY') == '1'
        assert env.get('DOCKER_CERT_PATH') == '/certs/client'
        sab_vols = sablier.get('volumes', [])
        assert any(str(ca) + ':/certs/client/ca.pem:ro' == v for v in sab_vols)
        assert any(str(cert) + ':/certs/client/cert.pem:ro' == v for v in sab_vols)
        assert any(str(key) + ':/certs/client/key.pem:ro' == v for v in sab_vols)
        assert not any('/var/run/docker.sock' in v for v in sab_vols)
        # Check container-lock env and volumes
        cl = data['services']['container-lock']
        env2 = cl.get('environment', {})
        assert env2.get('DOCKER_HOST') == 'tcp://docker.example.com:2376'
        assert env2.get('DOCKER_TLS_VERIFY') == '1'
        assert env2.get('DOCKER_CERT_PATH') == '/certs/client'
        cl_vols = cl.get('volumes', [])
        assert any(str(ca) + ':/certs/client/ca.pem:ro' == v for v in cl_vols)
        assert any(str(cert) + ':/certs/client/cert.pem:ro' == v for v in cl_vols)
        assert any(str(key) + ':/certs/client/key.pem:ro' == v for v in cl_vols)
        assert not any('/var/run/docker.sock' in v for v in cl_vols)
    finally:
        # Clean generated output to avoid interfering with other tests
        if os.path.isdir('output'):
            shutil.rmtree('output')
        os.chdir(cwd) 