"""Cache preflight/HTTP regressions; run with the GUI's Python dependencies."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'sifter_vis_d3/server'))
from cache_limits import (CacheBudgetExceeded, CacheRequestError,
                          check_cache_budget, validate_cache_geometry)
from sampler import Sampler
import server


class CacheLimitsTest(unittest.TestCase):
    def test_geometry_matches_configured_cache(self):
        self.assertEqual(validate_cache_geometry(4096, 64, 2000, 2**21, 8), 4096)
        for args in ((4096, 0, 2000, 32768, 8), (4096, 64, 0, 32768, 8),
                     (4096, 64, 2000, 32769, 8), (4096, 64, 2.5, 32768, 8)):
            with self.assertRaises(CacheRequestError):
                validate_cache_geometry(*args)

    @patch.dict(os.environ, {'HEAPLENS_CACHE_BUDGET_MB': '4096'})
    def test_budget(self):
        self.assertEqual(check_cache_budget(2000, 64, 245), 2002*64*245*96)
        with self.assertRaisesRegex(CacheBudgetExceeded, 'Try 42 or fewer time buckets'):
            check_cache_budget(2000, 4096, 245)
        self.assertLess(check_cache_budget(42, 4096, 245), 4096*1024**2)

    def test_bad_budget_setting(self):
        for value in ('', '0', '-1', 'no'):
            with patch.dict(os.environ, {'HEAPLENS_CACHE_BUDGET_MB': value}):
                with self.assertRaises(CacheRequestError):
                    check_cache_budget(1, 1, 1)

    @patch.dict(os.environ, {'HEAPLENS_CACHE_BUDGET_MB': '4096'})
    def test_error_explains_budget_override_without_changing_geometry(self):
        import re
        with self.assertRaises(CacheBudgetExceeded) as caught:
            check_cache_budget(1000, 64, 982)
        message = str(caught.exception)
        required = int(re.search(r'HEAPLENS_CACHE_BUDGET_MB=(\d+)', message).group(1))
        self.assertIn('additional memory for the server and browser', message)
        with patch.dict(os.environ, {'HEAPLENS_CACHE_BUDGET_MB': str(required)}):
            self.assertEqual(check_cache_budget(1000, 64, 982), 1002*64*982*96)

    @patch.dict(os.environ, {'HEAPLENS_CACHE_BUDGET_MB': '4096'})
    def test_guard_precedes_dense_allocation(self):
        sampler = Sampler.__new__(Sampler)
        sampler.page_size, sampler.cache_line_size, sampler.num_buckets = 4096, 64, 2000
        sampler.all_data = None
        sampler.get_objects = Mock()
        sampler.types = Mock(return_value=[str(i) for i in range(245)])
        sampler.get_fields = Mock(return_value={})
        with patch('sampler.np.empty') as allocate:
            with self.assertRaises(CacheBudgetExceeded):
                sampler.get_cache_data(2**21, 8)
            allocate.assert_not_called()

    def test_http_errors_and_recovery(self):
        client = server.app.test_client()
        with patch('server.Sampler') as factory:
            bad = client.get('/get-cache-data/example.sqlite-4096-64-0-32768-8')
            self.assertEqual(bad.status_code, 400)
            factory.assert_not_called()
            sampler = factory.return_value
            sampler.types.return_value = []
            sampler.get_all_lines_and_stats.return_value = {}
            sampler.get_sample_of_pages.return_value = {}
            sampler.get_cache_data.side_effect = CacheBudgetExceeded('budget exceeded')
            response = client.get('/get-cache-data/example.sqlite-4096-64-2000-2097152-8')
            self.assertEqual(response.status_code, 413)
            self.assertEqual(response.json, {'error': 'budget exceeded'})
            self.assertEqual(client.get('/init-app/example.sqlite-4096-64-2000-mbkmeans-5-3-2097152-8').status_code, 413)
            self.assertEqual(client.post('/get-pages-and-cache-data/example.sqlite-4096-64-2000-mbkmeans-5-3-2097152-8', json={}).status_code, 413)
            sampler.get_cache_data.side_effect = MemoryError()
            self.assertEqual(client.get('/get-cache-data/example.sqlite-4096-64-2000-32768-8').status_code, 503)
            sampler.get_cache_data.side_effect = None
            sampler.get_cache_data.return_value = {'occ': [], 'idxToTpAndSt': [], 'numSets': 64}
            self.assertEqual(client.get('/get-cache-data/example.sqlite-4096-64-20-32768-8').status_code, 200)


if __name__ == '__main__':
    unittest.main()
