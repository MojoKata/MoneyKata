"""The server's own zone, read from the host (requirements S14.9.2)."""

from pathlib import Path
from zoneinfo import TZPATH

from moneykata.timezones import zone_of


def test_a_mounted_localtime_is_known_by_its_content():
    # compose.yaml mounts the host's /etc/localtime as a file, not a link to a named zone.
    denver = next(Path(p) / "America/Denver" for p in TZPATH if (Path(p) / "America").is_dir())
    assert zone_of(denver.read_bytes()) == "America/Denver"
    assert zone_of(b"not a zone") == ""
