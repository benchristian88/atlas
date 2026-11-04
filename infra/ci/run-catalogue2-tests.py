"""Catalogue 2 plus existing root/security acceptance in disposable CI Docker."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from xml.etree import ElementTree

from importlib.util import spec_from_file_location, module_from_spec
spec = spec_from_file_location('local_tests', Path(__file__).with_name('run-local-release-tests.py'))
local = module_from_spec(spec)
spec.loader.exec_module(local)


def main():
    assert os.geteuid() == 0 and Path('/.dockerenv').exists(), 'Use isolated CI Docker'
    # Root test API lifespans need a root-owned private test state directory.
    # The production image keeps its service-account-owned directory intact.
    os.environ['ATLAS_STATE_DIR'] = tempfile.mkdtemp(prefix='atlas-catalogue2-state-')
    local.prepare_database()
    report = Path('/tmp/atlas-ci-catalogue2.xml')
    modules = (*local.TEST_MODULES, 'test_catalogue_future', 'test_remote_connector_packages',
               'test_catalogue_request_budget', 'test_integration_catalogue_api')
    subprocess.run([sys.executable, '-m', 'pytest', *(f'tests/{name}.py' for name in modules),
        '-q', '-rs', '--tb=short', f'--junitxml={report}'], check=True)
    cases = ElementTree.parse(report).findall('.//testcase')
    assert len(cases) >= 150 and all(len(case) == 0 for case in cases), 'No skips, errors or failures permitted'
    print(f'Catalogue 2 Docker security/installation acceptance: {len(cases)} passed; zero skipped', flush=True)


if __name__ == '__main__':
    main()
