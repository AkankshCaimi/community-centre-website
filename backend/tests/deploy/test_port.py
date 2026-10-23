"""Starting the server on the host's port: rules P1 to P4 of docs/specs/deploy-free.md.

Every expected value comes from that spec; each test names the rule it checks.
"""

import json
import runpy
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
SETTINGS = BACKEND / "gunicorn.conf.py"
DOCKERFILE = BACKEND.parent / "Dockerfile"


def load_settings(monkeypatch, port):
    """The names defined by the gunicorn settings file, with PORT set to `port` (None: unset)."""
    if port is None:
        monkeypatch.delenv("PORT", raising=False)
    else:
        monkeypatch.setenv("PORT", port)
    return runpy.run_path(str(SETTINGS))


def default_command():
    """The exec-form CMD of the Dockerfile, as a list."""
    lines = [line for line in DOCKERFILE.read_text().splitlines() if line.startswith("CMD ")]
    assert len(lines) == 1
    return json.loads(lines[0][len("CMD ") :])


# --- P1: bind to 0.0.0.0 on PORT


@pytest.mark.parametrize("port", ["8080", "10000", "1", "65535"])
def test_p1_binds_all_interfaces_on_port(monkeypatch, port):
    assert load_settings(monkeypatch, port)["bind"] == f"0.0.0.0:{port}"


def test_p1_settings_file_is_in_the_backend_folder():
    assert SETTINGS.is_file()


def test_p1_image_copies_the_settings_file_to_the_working_directory():
    text = DOCKERFILE.read_text()
    assert "WORKDIR /app/backend" in text
    assert any(
        line.startswith("COPY ") and line.split()[1:] == ["backend/gunicorn.conf.py", "./"]
        for line in text.splitlines()
    )


def test_p1_default_command_uses_the_settings_file():
    command = default_command()
    assert command[0] == "gunicorn"
    assert command[command.index("--config") + 1] == "gunicorn.conf.py"


# --- P2: 8000 without PORT


@pytest.mark.parametrize("port", [None, ""])
def test_p2_without_port_binds_8000(monkeypatch, port):
    assert load_settings(monkeypatch, port)["bind"] == "0.0.0.0:8000"


# --- P3: a PORT that is not a whole number from 1 to 65535 stops the start


@pytest.mark.parametrize("port", ["abc", "0", "65536", "-1", "80.5", " 8080", "8080 ", "+80", "٨٠"])
def test_p3_bad_port_is_refused_naming_port(monkeypatch, port):
    with pytest.raises(Exception) as error:
        load_settings(monkeypatch, port)
    assert "PORT" in str(error.value)


# --- P4: 2 workers, no control socket, no access log, no --bind


def test_p4_two_workers():
    command = default_command()
    assert command[command.index("--workers") + 1] == "2"


def test_p4_no_control_socket():
    assert "--no-control-socket" in default_command()


def test_p4_no_bind_on_the_command_line():
    assert not any(arg == "-b" or arg.startswith("--bind") for arg in default_command())


def test_p4_no_access_log(monkeypatch):
    assert not any(arg.startswith("--access-log") for arg in default_command())
    assert load_settings(monkeypatch, "8080").get("accesslog") is None


def test_p4_app_is_unchanged():
    assert default_command()[-1] == "app:create_app()"
