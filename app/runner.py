import json, time, unittest
from pathlib import Path
from django.test.runner import DiscoverRunner

class EvidenceResult(unittest.TextTestResult):
    records=[]
    def startTest(self,test): self.started=time.perf_counter(); super().startTest(test)
    def record(self,test,status):
        self.records.append({'test':test.id(),'status':status,'seconds':round(time.perf_counter()-self.started,4)})
    def addSuccess(self,test): super().addSuccess(test); self.record(test,'passed')
    def addFailure(self,test,err): super().addFailure(test,err); self.record(test,'failed')
    def addError(self,test,err): super().addError(test,err); self.record(test,'error')

class EvidenceRunner(DiscoverRunner):
    def get_resultclass(self): return EvidenceResult
    def suite_result(self,suite,result,**kwargs):
        Path('evidence').mkdir(exist_ok=True)
        Path('evidence/tests.json').write_text(json.dumps({'database':'PostgreSQL','tests':EvidenceResult.records,'passed':result.wasSuccessful(),'run_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()},indent=2))
        return super().suite_result(suite,result,**kwargs)
