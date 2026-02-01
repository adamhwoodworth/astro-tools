import subprocess
import shutil
from pathlib import Path
import pytest


FIXTURES_DIR = Path(__file__).parent / 'fixtures'
CACHE_DIR = Path('cache')


def normalize_output(output):
    """Remove cache status lines from output for comparison."""
    lines = output.split('\n')
    filtered = [line for line in lines if not line.strip().startswith(('Using cached data', 'Downloading from USNO', 'Saved to cache'))]
    return '\n'.join(filtered)


@pytest.fixture(scope='session', autouse=True)
def cleanup_cache():
    """Remove all cache files before any tests run."""
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    yield


def test_darknights_2026_jun_no_cache():
    """Test darknights.py without cache."""
    result = subprocess.run(
        ['uv', 'run', 'darknights.py', '2026', 'jun', '--no-color', '--no-cache'],
        capture_output=True,
        text=True,
        timeout=120
    )
    assert result.returncode == 0, f"Command failed with stderr: {result.stderr}"

    # Verify cache status messages
    assert '  Downloading from USNO...' in result.stdout
    assert 'Saved to cache' not in result.stdout  # --no-cache shouldn't save

    # Verify output matches expected (ignoring cache status lines)
    expected = (FIXTURES_DIR / 'expected_output_2026_jun.txt').read_text()
    assert normalize_output(result.stdout) == normalize_output(expected)


def test_darknights_2026_jun_with_cache():
    """Test darknights.py with cache (should create cache files)."""
    result = subprocess.run(
        ['uv', 'run', 'darknights.py', '2026', 'jun', '--no-color'],
        capture_output=True,
        text=True,
        timeout=120
    )
    assert result.returncode == 0, f"Command failed with stderr: {result.stderr}"

    # Verify cache status messages
    assert '  Downloading from USNO...' in result.stdout
    assert '  Saved to cache' in result.stdout

    # Verify output matches expected (ignoring cache status lines)
    expected = (FIXTURES_DIR / 'expected_output_2026_jun.txt').read_text()
    assert normalize_output(result.stdout) == normalize_output(expected)

    # Verify cache files were created
    assert CACHE_DIR.exists(), "Cache directory should exist"
    cache_files = list(CACHE_DIR.glob('*.html'))
    assert len(cache_files) == 3, f"Expected 3 cache files, found {len(cache_files)}"


def test_darknights_2026_jun_with_cache_reuse():
    """Test darknights.py with cache again (should reuse existing cache)."""
    result = subprocess.run(
        ['uv', 'run', 'darknights.py', '2026', 'jun', '--no-color'],
        capture_output=True,
        text=True,
        timeout=120
    )
    assert result.returncode == 0, f"Command failed with stderr: {result.stderr}"

    # Verify cache status messages
    assert '  Using cached data' in result.stdout
    assert 'Downloading from USNO' not in result.stdout

    # Verify output matches expected (ignoring cache status lines)
    expected = (FIXTURES_DIR / 'expected_output_2026_jun.txt').read_text()
    assert normalize_output(result.stdout) == normalize_output(expected)


def test_darknights_2026_jun_no_cache_again():
    """Test darknights.py without cache again (cache should be ignored)."""
    result = subprocess.run(
        ['uv', 'run', 'darknights.py', '2026', 'jun', '--no-color', '--no-cache'],
        capture_output=True,
        text=True,
        timeout=120
    )
    assert result.returncode == 0, f"Command failed with stderr: {result.stderr}"

    # Verify cache status messages
    assert '  Downloading from USNO...' in result.stdout
    assert 'Using cached data' not in result.stdout  # --no-cache should bypass cache

    # Verify output matches expected (ignoring cache status lines)
    expected = (FIXTURES_DIR / 'expected_output_2026_jun.txt').read_text()
    assert normalize_output(result.stdout) == normalize_output(expected)
