"""Isolated behavior checks; no Django imports, database or network access."""
import ast
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
class Conflict(Exception): pass
class Invalid(Exception): pass
def identity_atomic(function): return function

class WaveTwoBackendTests(unittest.TestCase):
    def overtime(self, current):
        tree=ast.parse((ROOT/'core/views_staff_requests.py').read_text(encoding='utf-8'))
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='decide_overtime')
        slip=SimpleNamespace(pk='id',employee='owner',hours=Decimal('2'),multiplier=Decimal('1.5'),status='Pending')
        saves=[];slip.save=lambda **kwargs:saves.append(kwargs)
        query=SimpleNamespace(select_related=lambda *args:None)
        namespace={'transaction':SimpleNamespace(atomic=identity_atomic),'require_hr':lambda user:None,
            'get_object_or_404':lambda *args,**kwargs:slip,
            'OvertimeSlip':SimpleNamespace(objects=SimpleNamespace(select_for_update=lambda:query)),
            'ensure_pending':lambda obj:None,'ValidationError':Invalid,'Conflict409':Conflict,
            'current_overtime_values':lambda obj:current,'audit':lambda *args:None}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<overtime>','exec'),namespace)
        return namespace['decide_overtime'],slip,saves

    def test_stale_values_cannot_be_approved(self):
        decide,slip,saves=self.overtime((Decimal('1'),Decimal('1.5')))
        with self.assertRaises(Conflict): decide('id','Approved','HR')
        self.assertEqual(slip.status,'Pending');self.assertEqual(saves,[])

    def test_no_longer_eligible_cannot_be_approved(self):
        decide,slip,saves=self.overtime((Decimal('0'),Decimal('1.5')))
        with self.assertRaises(Conflict): decide('id','Approved','HR')
        self.assertEqual(slip.status,'Pending');self.assertEqual(saves,[])

    def test_current_values_approve_and_invalid_sources_can_be_rejected(self):
        decide,slip,saves=self.overtime((Decimal('2'),Decimal('1.5')))
        decide('id','Approved','HR');self.assertEqual(slip.status,'Approved')
        decide,slip,saves=self.overtime(None)
        decide('id','Rejected','HR');self.assertEqual(slip.status,'Rejected')

    def test_settings_validate_whole_batch_before_writes(self):
        tree=ast.parse((ROOT/'core/views.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SiteSettingsView')
        function=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='patch')
        function.body=[n for n in function.body if not isinstance(n,ast.ImportFrom)]
        writes=[]
        class Serializer:
            def __init__(self,data): self.data=data
            def is_valid(self,**kwargs):
                if self.data['key']=='invalid': raise Invalid()
        namespace={'transaction':SimpleNamespace(atomic=identity_atomic),'SiteSettingSerializer':Serializer,
            'SiteSetting':SimpleNamespace(objects=SimpleNamespace(get_or_create=lambda **kwargs:writes.append(kwargs))),
            'SITE_SETTING_DEFAULTS':{}}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<settings>','exec'),namespace)
        with self.assertRaises(Invalid): namespace['patch'](None,SimpleNamespace(data={'valid':'4','invalid':'bad'}))
        self.assertEqual(writes,[])

    def test_recalculation_updates_values_but_does_not_approve(self):
        tree=ast.parse((ROOT/'core/views_staff_requests.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='OvertimeRecalculateView')
        function=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='post')
        slip=SimpleNamespace(pk='id',employee='owner',status='Pending',hours=Decimal('2'),multiplier=Decimal('1.5'),save=lambda **kwargs:None)
        namespace={'transaction':SimpleNamespace(atomic=identity_atomic),'require_hr':lambda user:None,
            'get_object_or_404':lambda *args,**kwargs:slip,
            'OvertimeSlip':SimpleNamespace(objects=SimpleNamespace(select_for_update=lambda:None)),
            'ensure_pending':lambda obj:None,'current_overtime_values':lambda obj:(Decimal('1'),Decimal('1.25')),
            'audit':lambda *args:None,'OvertimeSlipSerializer':lambda obj,**kwargs:SimpleNamespace(data={'status':obj.status,'hours':obj.hours}),
            'Response':lambda data:data}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<recalculate>','exec'),namespace)
        result=namespace['post'](None,SimpleNamespace(user='HR'),'id')
        self.assertEqual(result,{'status':'Pending','hours':Decimal('1')})

if __name__=='__main__': unittest.main()
