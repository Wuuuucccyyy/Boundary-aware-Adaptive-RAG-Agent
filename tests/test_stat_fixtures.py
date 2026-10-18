import json
from pathlib import Path
import statistics as st
import tempfile
import unittest
from unittest.mock import patch
from stat_rag import fixtures


class StatisticalFixtureTests(unittest.TestCase):
    def test_studies_rebuild_exactly(self):
        expected=(fixtures.DATA/'studies.json').read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(fixtures,'DATA',Path(directory)):fixtures.build()
            self.assertEqual(expected,Path(directory,'studies.json').read_bytes())

    def test_trial_value_matches_raw_randomized_data(self):
        sources=json.loads((fixtures.DATA/'studies.json').read_text(encoding='utf-8'))
        for s in sources:
            if s['kind']!='trial':continue
            d=s['computation'];a=d['treatment'];y=d['outcome']
            difference=st.mean(v for v,t in zip(y,a) if t)-st.mean(v for v,t in zip(y,a) if not t)
            self.assertIn(f'{difference:.3f}',s['document']['quote'])

    def test_nested_snapshot_keeps_support_documents(self):
        from stat_rag.core import Corpus
        a=Corpus(10);b=Corpus(30)
        self.assertEqual(a.sources,b.sources[:10])
        self.assertEqual(len(set(s['id'] for s in b.sources)),30)


if __name__=='__main__':unittest.main()
