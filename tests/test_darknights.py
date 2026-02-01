import subprocess
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent / 'fixtures'


def test_darknights_2026_jun():
    """Test that darknights.py produces expected output for June 2026."""
    result = subprocess.run(
        ['uv', 'run', 'darknights.py', '2026', 'jun', '--no-color', '--no-cache'],
        capture_output=True,
        text=True,
        timeout=120
    )
    assert result.returncode == 0, f"Command failed with stderr: {result.stderr}"

    expected = (FIXTURES_DIR / 'expected_output_2026_jun.txt').read_text()
    assert result.stdout == expected
