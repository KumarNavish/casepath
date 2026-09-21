"""Keep retained provider payloads out of per-cell status checks."""
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from casepath_api.obligation_control.study_v1.journal import Journal

class JournalProjectionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.journal=Journal(Path(self.tmp.name)/'journal.sqlite');self.queries=[]
  original=self.journal.connect
  @contextmanager
  def traced():
   with original() as db:
    db.set_trace_callback(self.queries.append);yield db
  self.journal.connect=traced
  with self.journal.connect() as db:
   db.execute('INSERT INTO requests VALUES(?,?,?,?,?,?)',('r','p','slot','1','completed','.03'))
   self.journal._event(db,'p','r','REQUEST_STARTED',{'payload':'x'*2_000_000})
   self.journal._event(db,'p','r','OBSERVATION',{'evidence':{'receipt_sha256':'old'}})
   self.journal._event(db,'p','r','OBSERVATION',{'evidence':{'receipt_sha256':'latest'}})
   self.journal._event(db,'p','unrelated','OBSERVATION',{'evidence':{'receipt_sha256':'other'}})
  self.queries.clear()
 def tearDown(self):self.tmp.cleanup()
 def test_status_projection_does_not_select_events(self):
  summary=self.journal.facts('p',include_events=False)
  self.assertEqual(summary['known_cost_usd'],'0.03')
  self.assertNotIn('events',summary)
  self.assertFalse(any('FROM EVENTS' in q.upper() for q in self.queries))
 def test_latest_observation_is_request_scoped(self):
  self.assertEqual(self.journal.last_observation('r'),{'evidence':{'receipt_sha256':'latest'}})
  self.assertEqual(len(self.queries),1)
  self.assertIn('LIMIT 1',self.queries[0].upper())
 def test_missing_observation_is_not_fabricated(self):self.assertIsNone(self.journal.last_observation('absent'))
 def test_full_export_preserves_all_history(self):
  full=self.journal.facts('p');self.assertEqual(len(full['events']),4)
  self.assertIn('x'*100,full['events'][0]['body'])
  self.queries.clear();summary=self.journal.facts('p',include_events=False)
  self.assertEqual(summary,{k:v for k,v in full.items() if k!='events'})
if __name__=='__main__':unittest.main()
