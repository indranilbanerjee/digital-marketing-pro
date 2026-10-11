"""Calendar-unit and already-crossed regression coverage, with no account access."""
import importlib.util
import json
import subprocess
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

scripts = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location('fatigue_calendar', scripts / 'creative-fatigue-predictor.py')
predictor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(predictor)


class CalendarForecastTests(unittest.TestCase):
    def history(self, rates, interval=1, cpms=None):
        return [{'date': (date(2026, 1, 1) + timedelta(days=i * interval)).isoformat(),
                 'ctr': ctr, 'cpm': cpms[i] if cpms else 10}
                for i, ctr in enumerate(rates)]

    def test_daily_remaining_starts_at_last_observation(self):
        result = predictor.predict_fatigue('test', self.history([.10, .095, .09]))
        self.assertEqual(result['days_remaining'], 4)
        self.assertEqual(result['predicted_fatigue_date'], '2026-01-07')

    def test_weekly_history_uses_elapsed_days(self):
        result = predictor.predict_fatigue('test', self.history([.10, .095, .09], 7))
        self.assertEqual(result['days_remaining'], 28)
        self.assertEqual(result['predicted_fatigue_date'], '2026-02-12')

    def test_irregular_intervals_use_dates(self):
        history = [{'date': '2026-01-01', 'ctr': .10, 'cpm': 10},
                   {'date': '2026-01-03', 'ctr': .098, 'cpm': 10},
                   {'date': '2026-01-11', 'ctr': .09, 'cpm': 10}]
        result = predictor.predict_fatigue('test', history)
        self.assertEqual(result['days_remaining'], 20)
        self.assertEqual(result['predicted_fatigue_date'], '2026-01-31')

    def test_future_cpm_crossing(self):
        result = predictor.predict_fatigue('test', self.history([.10] * 3, cpms=[10, 11, 12]))
        self.assertEqual(result['days_remaining'], 1)

    def test_crossed_ctr_even_when_recovering(self):
        for rates in ([.10, .07, .04], [.10, .03, .05]):
            result = predictor.predict_fatigue('test', self.history(rates))
            self.assertEqual(result['days_remaining'], 0)
            self.assertIn('threshold reached', result['recommendation'])

    def test_crossed_cpm(self):
        result = predictor.predict_fatigue('test', self.history([.10] * 3, cpms=[10, 12, 14]))
        self.assertEqual(result['days_remaining'], 0)

    def test_invalid_inputs_return_errors(self):
        valid = self.history([.10, .095, .09])
        cases = [None, {}, [None] * 3, list(reversed(valid)),
                 [valid[0], valid[0], valid[2]],
                 [dict(row, date=None) for row in valid],
                 [dict(row, date='bad') for row in valid],
                 [dict(row, ctr=float('nan')) for row in valid],
                 [dict(row, cpm=-1) for row in valid],
                 [dict(row, ctr=True) for row in valid],
                 [dict(row, ctr=0) for row in valid]]
        for history in cases:
            with self.subTest(history=history):
                self.assertIn('error', predictor.predict_fatigue('test', history))

    def test_flat_series_does_not_claim_proven_health(self):
        result = predictor.predict_fatigue('test', self.history([.10] * 3))
        self.assertIsNone(result['days_remaining'])
        self.assertIn('linear model', result['recommendation'])
        self.assertIn('not a statistical', result['confidence_basis'])

    def test_cli_rejects_invalid_history_with_nonzero_exit(self):
        result = subprocess.run([sys.executable, str(scripts / 'creative-fatigue-predictor.py'),
                                 '--action', 'predict-fatigue', '--creative-id', 'test',
                                 '--performance-history', json.dumps([None] * 3)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn('error', json.loads(result.stdout))


if __name__ == '__main__':
    unittest.main()
