from pathlib import Path
import pytest
from casepath_api import autonomous_api_v1

original = Path(__file__).with_name('api-before-lookahead-fix.py')
exec(compile(original.read_bytes(), str(original), 'exec'), autonomous_api_v1.__dict__)
raise SystemExit(pytest.main([
    '-q', '-p', 'no:cacheprovider', '--tb=short',
    'casepath-api/tests/test_autonomous_operations_v1.py', '-k', 'keeps_lookahead',
]))
