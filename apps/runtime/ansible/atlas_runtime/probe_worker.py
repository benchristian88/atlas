"""Private child entry point; no public path/command selection."""
import json
import os
from pathlib import Path
import sys

from .collections import execution_environment


def main():
    import ansible_runner
    os.umask(0o077)
    root = Path(sys.argv[1])
    payload = json.loads(sys.stdin.buffer.read(128 * 1024 + 1))
    # Source values never enter Ansible's templating/extravars/event system.
    # Only internal private paths are passed to the fixed verified playbook.
    with (root / "input.json").open("x") as inputs:
        json.dump(payload, inputs)
    payload.clear()
    result = ansible_runner.run(private_data_dir=str(root), playbook="test_connection.yml",
        inventory="localhost,", quiet=True,
        extravars={"atlas_input_file": str(root / "input.json"),
            "atlas_result_file": str(root / "result.json"), "ansible_python_interpreter": sys.executable},
        envvars={**execution_environment(), "ANSIBLE_LOCAL_TEMP": str(root / "local-tmp"), "ANSIBLE_REMOTE_TEMP": str(root / "remote-tmp"),
            "ANSIBLE_RETRY_FILES_ENABLED": "False", "ANSIBLE_NOCOLOR": "True"},
        settings={"job_timeout": 20, "idle_timeout": 20, "suppress_output_file": True,
            "suppress_ansible_output": True, "omit_event_data": True},
        event_handler=lambda _event: False)
    payload.clear()
    raise SystemExit(0 if result.rc == 0 else 1)


if __name__ == "__main__":
    main()
