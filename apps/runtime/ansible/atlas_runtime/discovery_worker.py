"""Fixed private child. Connector input contains no Atlas authentication secret."""
import json
import os
from pathlib import Path
import resource
import sys


def main():
    import ansible_runner
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    root = Path(sys.argv[1])
    payload = json.loads(sys.stdin.buffer.read(128 * 1024 + 1))
    timeout = payload["timeout_seconds"] - 35
    with (root / "input.json").open("x") as inputs:
        json.dump(payload, inputs, allow_nan=False)
    payload.clear()
    result = ansible_runner.interface.init_runner(private_data_dir=str(root), playbook="discover.yml", inventory="localhost,", quiet=True,
        extravars={"atlas_input_file": str(root / "input.json"), "atlas_aip_file": str(root / "aip.ndjson"),
            "ansible_python_interpreter": sys.executable},
        envvars={"ANSIBLE_LOCAL_TEMP": str(root / "local-tmp"), "ANSIBLE_REMOTE_TEMP": str(root / "remote-tmp"),
            "ANSIBLE_RETRY_FILES_ENABLED": "False", "ANSIBLE_NOCOLOR": "True"},
        settings={"job_timeout": timeout, "idle_timeout": timeout, "suppress_output_file": True,
            "suppress_ansible_output": True, "omit_event_data": True}, event_handler=lambda _event: False)
    # pexpect creates a separate session. The subprocess runner keeps the
    # playbook and local module children in this worker's killable process group.
    result.runner_mode = result.config.runner_mode = "subprocess"
    result.config.subprocess_timeout = timeout
    result.run()
    raise SystemExit(0 if result.rc == 0 else 1)


if __name__ == "__main__":
    main()
