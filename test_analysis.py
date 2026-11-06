import sys,json,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'vendor'))
import numpy as np
import community as cm
from model import Simulation
from export_analysis import save


def fixture():
    a=np.zeros((10,10),bool)
    for u,v in [(1,2),(1,3),(2,3),(2,10),(3,10),(4,5),(4,6),(5,6),(2,7),(7,5),(1,8)]:a[u-1,v-1]=a[v-1,u-1]=True
    d=cm.Detector(.4,starts=12);d.detect(a)
    traits={k:np.full(10,.5) for k in ('form','cut','receive','spread')}
    return a,d,traits


class AnalysisChecks(unittest.TestCase):
    def test_ten_people_fixture(self):
        a,d,t=fixture();x=np.full((10,10),.6);np.fill_diagonal(x,0)
        rows=cm.roles(a,x,d,t)
        self.assertAlmostEqual(d.score,4.4)
        self.assertEqual(set(d.groups),{(0,1,2,9),(3,4,5)})
        self.assertTrue(rows[1]['hub']);self.assertTrue(rows[2]['hub'])
        self.assertEqual(rows[1]['brokerage_disconnected_pairs'],9)
        self.assertEqual(rows[6]['brokerage_disconnected_pairs'],12)
        self.assertEqual(rows[2]['brokerage_disconnected_pairs'],0)
        self.assertFalse(rows[1]['multi_community_connector'])
        self.assertTrue(rows[6]['multi_community_connector'])
        self.assertEqual(rows[6]['base_status'],'unassigned_connected')
        self.assertEqual(rows[7]['base_status'],'unassigned_connected')
        self.assertEqual(rows[8]['base_status'],'isolated')
        self.assertTrue(rows[1]['high_liking'])
        self.assertAlmostEqual(rows[1]['internal_ratio'],1)
        np.testing.assert_array_equal(a,a.T)

    def test_dyad_and_uniform_clique(self):
        from test_model import adjacency
        a=adjacency(7,[(i,j) for i in range(4) for j in range(i+1,4)]+[(4,5)])
        d=cm.Detector();d.detect(a);t={k:np.full(7,.5) for k in ('form','cut','receive','spread')}
        rows=cm.roles(a,np.zeros((7,7)),d,t)
        self.assertEqual(rows[4]['base_status'],'dyad');self.assertIsNone(rows[4]['community'])
        self.assertFalse(any(r['hub'] for r in rows));self.assertIsNone(rows[6]['internal_ratio'])
        changed=cm.roles(a,np.zeros((7,7)),d,t,rules={'community_min':5})
        self.assertEqual(changed[0]['base_status'],'unassigned_connected')

    def test_alternate_path_removes_essential_broker(self):
        a,d,t=fixture();a[0,3]=a[3,0]=True
        raw=np.array([0,0,0,1,1,1,2,3,4,0])
        rows=cm.structural_metrics(a,np.zeros((10,10)),raw,cm.ROLE_DEFAULTS)
        self.assertEqual(rows[6]['brokerage_disconnected_pairs'],0)
        self.assertTrue(rows[6]['multi_community_connector'])

    def test_analysis_read_only_and_reanalysis(self):
        s=Simulation(12);s.act('harm',0,1)
        for _ in range(12):s.step()
        x=s.world.x.copy();a=s.world.a.copy()
        report=s.summary();snap=s.snapshot()
        np.testing.assert_array_equal(x,s.world.x);np.testing.assert_array_equal(a,s.world.a)
        rows=cm.reanalyze_snapshot(snap['snapshots'][-1],report['rules'])
        for r,original in zip(rows,report['people']):
            self.assertEqual(r['roles'],original['roles'])
            self.assertEqual(r['brokerage_disconnected_pairs'],original['brokerage_disconnected_pairs'])
        self.assertEqual(snap['snapshots'][0]['reason'],'initial')
        self.assertTrue(any(e['kind']=='action' for e in snap['timeline']))

    def test_initial_attributes_and_isolation_transition(self):
        s=Simulation(12);initial=s.world.role_rows()[0]['formation']
        s.edit_person(0,.8,.2,.6,.9)
        r=s.world.role_rows()[0]
        self.assertAlmostEqual(r['initial_attributes']['formation'],initial)
        self.assertAlmostEqual(r['formation'],.8)
        self.assertIn(r['isolation_transition'],['孤立継続','関係獲得','孤立化','関係維持・再編'])

    def test_full_export(self):
        s=Simulation(8);s.act('gossip',0,1)
        for _ in range(3):s.step()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(save(s,tmp))
            for name in ('runs.csv','agents.csv','agent_communities.csv','communities.csv','events.csv','person_comparison.csv','snapshots.json'):self.assertTrue((path/name).is_file())
            data=json.loads((path/'snapshots.json').read_text(encoding='utf-8'))
            self.assertEqual(data['analysis_version'],'2.1')
            self.assertEqual(len(data['snapshots']),5)
            self.assertTrue(data['baseline_snapshots'])
            self.assertEqual(len(data['analysis']['person_comparison']),8)

    def test_role_uncertainty_from_tied_partitions(self):
        from test_model import adjacency
        a=adjacency(8,[(0,1),(0,2),(1,2),(3,4),(3,5),(4,5),(2,3),(1,6),(4,6)])
        d=cm.Detector(starts=24);d.detect(a)
        t={k:np.full(8,.5) for k in ('form','cut','receive','spread')}
        rows=cm.roles(a,np.zeros((8,8)),d,t)
        self.assertTrue(any(r['role_uncertain'] for r in rows))

    def test_shared_sources_have_separate_transmission_credit(self):
        s=Simulation(4,settings={'pmax':1,'witnesses':0,'q0':0,'qtri':0})
        w=s.world;w.a[:]=True;np.fill_diagonal(w.a,False)
        w.x[:]=.8;np.fill_diagonal(w.x,0);w.traits['spread'][:]=1
        w.act('harm',0,1,.1);w.advance()
        rows=w.role_rows()
        self.assertEqual(sum(r['successful_transmissions'] for r in rows),4)
        self.assertAlmostEqual(sum(r['transmission_credit'] for r in rows),2.)
        self.assertTrue(any(e.get('mechanism')=='information' for e in w.timeline))


if __name__=='__main__':unittest.main()
