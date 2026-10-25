import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("working_directory", [".", "backend", "unrelated"])
@pytest.mark.parametrize("returncode", [0, 1], ids=["success", "promtool-failure"])
def test_backfill_uses_compose_data_and_repository_scratch_from_any_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    working_directory: str,
    returncode: int,
) -> None:
    # Copy the relocated script so all filesystem effects stay in a disposable checkout.
    repository = tmp_path / "checkout"
    script = repository / "backend/scripts/seed_demo_data.py"
    script.parent.mkdir(parents=True)
    source = Path(__file__).parents[3] / "scripts/seed_demo_data.py"
    shutil.copyfile(source, script)
    cwd = (
        tmp_path / "unrelated"
        if working_directory == "unrelated"
        else repository / working_directory
    )
    cwd.mkdir(exist_ok=True)
    monkeypatch.chdir(cwd)

    spec = importlib.util.spec_from_file_location("seed_paths_test", script)
    assert spec is not None and spec.loader is not None
    seeder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seeder)

    scratch_directories: list[Path] = []
    openmetrics = "# EOF\n"

    def run_promtool(
        command: list[str], *, capture_output: bool, text: bool, check: bool
    ) -> subprocess.CompletedProcess[str]:
        staging = Path(command[command.index("-v") + 1].removesuffix(":/w"))
        scratch_directories.append(staging)
        assert staging.parent == repository
        assert staging.name.startswith("seed-")
        assert (staging / "in.om").read_text() == openmetrics
        assert (staging / "out").is_dir()
        assert command == [
            "docker",
            "run",
            "--rm",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{staging}:/w",
            "--entrypoint",
            "promtool",
            "prom/prometheus:v3.13.5",
            "tsdb",
            "create-blocks-from",
            "openmetrics",
            "/w/in.om",
            "/w/out",
        ]
        assert capture_output and text and not check
        if returncode == 0:
            block = staging / "out/01DEMO_BLOCK"
            block.mkdir()
            (block / "meta.json").write_text('{"demo": true}\n')
        return subprocess.CompletedProcess(command, returncode, "", "synthetic failure")

    monkeypatch.setattr(seeder.subprocess, "run", run_promtool)
    if returncode == 0:
        seeder.backfill_metrics(openmetrics, seeder.PROM_DATA)
        metadata = repository / "docker/prometheus/data/01DEMO_BLOCK/meta.json"
        assert metadata.read_text() == '{"demo": true}\n'
    else:
        with pytest.raises(RuntimeError, match="promtool backfill failed: synthetic failure"):
            seeder.backfill_metrics(openmetrics, seeder.PROM_DATA)
        assert list((repository / "docker/prometheus/data").iterdir()) == []

    assert len(scratch_directories) == 1
    assert not scratch_directories[0].exists()
    assert not (repository / "backend/docker").exists()
