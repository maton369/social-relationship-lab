import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'vendor'))
import unittest
import numpy as np
import community as cm
from model import Simulation,World,draw,update_ties


def adjacency(n,edges):
    a=np.zeros((n,n),bool)
    for i,j in edges:a[i,j]=a[j,i]=True
    return a


class Checks(unittest.TestCase):
    def test_bridge_does_not_merge_triangles(self):
        a=adjacency(7,[(0,1),(0,2),(1,2),(3,4),(3,5),(4,5),(2,3)])
        d=cm.Detector();d.detect(a)
        self.assertEqual(set(d.groups),{(0,1,2),(3,4,5)})
        self.assertEqual(d.labels[6],-1)
        self.assertAlmostEqual(d.score,4.5)

    def test_eight_person_quality_and_ambiguity(self):
        a=adjacency(8,[(0,1),(0,2),(1,2),(3,4),(3,5),(4,5),(2,3),(1,6),(4,6)])
        d=cm.Detector(starts=24);d.detect(a)
        self.assertAlmostEqual(d.score,4.75)
        self.assertTrue(d.ambiguous[6])
        before=d.raw.copy()
        d.detect(a,4)
        np.testing.assert_array_equal(before,d.raw)
        a[1,2]=a[2,1]=False;d.detect(a,5)
        self.assertAlmostEqual(d.score,3.75)

    def test_matching_and_label_invariance(self):
        matches=cm.assignment(np.array([[.9,.8],[.85,.1]]))
        self.assertEqual(set(matches),{(0,1),(1,0)})
        self.assertAlmostEqual(cm.partition_vi(np.array([1,1,4]),np.array([8,8,0])),0.)

    def test_temporal_split_confirmation_and_measurement_change(self):
        full=np.ones((6,6),bool);np.fill_diagonal(full,False)
        split=adjacency(6,[(0,1),(0,2),(1,2),(3,4),(3,5),(4,5)])
        d=cm.Detector();d.detect(full,0);d.detect(split,1)
        self.assertEqual(len(d.events),0)
        self.assertEqual(d.pending[0]['kind'],'split')
        d.detect(split,3);self.assertEqual(len(d.events),0)
        d.detect(split,4);self.assertEqual(d.events[0]['kind'],'split')
        d.detect(full,5);d.detect(full,8)
        self.assertEqual(d.events[-1]['kind'],'merge')
        d.detect(split,9,track_events=False)
        self.assertFalse(d.pending)
        self.assertEqual(len(d.events),2)

    def test_hysteresis(self):
        x=np.array([[0.,.7],[.4,0.]])
        zero=np.zeros((2,2),bool);op=np.array([[0,1],[1,0]],bool)
        self.assertFalse(update_ties(x,zero,np.array([.55,.55]),np.array([.25,.25]),op)[0,1])
        self.assertTrue(update_ties(x,op,np.array([.55,.55]),np.array([.25,.25]),zero)[0,1])
        x[1,0]=.25
        self.assertFalse(update_ties(x,op,np.array([.55,.55]),np.array([.25,.25]),zero)[0,1])

    def test_counterfactual_reproducibility_and_no_action(self):
        a,b=Simulation(12),Simulation(12)
        for _ in range(20):a.step();b.step()
        np.testing.assert_array_equal(a.world.x,a.base.x)
        np.testing.assert_array_equal(a.world.a,a.base.a)
        np.testing.assert_array_equal(a.world.a,b.world.a)
        self.assertEqual(draw(23,1,1,2,3),draw(23,1,1,2,3))

    def test_manual_mode_continues_past_stability_and_limit(self):
        s=Simulation(4,settings={'q0':0,'qtri':0,'limit':3,'window':2})
        for _ in range(12):self.assertTrue(s.step(enforce_limit=False))
        self.assertEqual(s.iteration,12)
        self.assertEqual(s.status,'absorbed')
        self.assertFalse(s.step())

    def test_no_spread_when_pmax_zero(self):
        s=Simulation(12,settings={'pmax':0,'witnesses':0,'q0':0,'qtri':0})
        s.act('harm',0,1,1.)
        expected=s.world.x.copy()
        for _ in range(15):s.step()
        np.testing.assert_array_equal(s.world.x,expected)
        self.assertEqual(s.world.events[0]['seen'].sum(),2)
        self.assertEqual(s.world.pending,0)
        self.assertEqual(s.status,'absorbed')

    def test_direct_effect_and_baseline(self):
        for kind,sign in [('help',1),('harm',-1)]:
            s=Simulation(12,settings={'witnesses':0})
            old=s.world.x.copy();base=s.base.x.copy()
            s.act(kind,0,1,.6)
            self.assertAlmostEqual(s.world.x[1,0],np.clip(old[1,0]+sign*.3,-1,1))
            self.assertEqual(s.world.x[0,1],old[0,1])
            np.testing.assert_array_equal(s.base.x,base)

    def test_simultaneous_sources_and_once_only(self):
        s=Simulation(4,settings={'pmax':1,'witnesses':0,'q0':0,'qtri':0})
        w=s.world
        w.a[:]=True;np.fill_diagonal(w.a,False)
        w.traits['spread'][:]=1;w.traits['receive'][:]=1
        w.x[:]=.8;np.fill_diagonal(w.x,0)
        w.act('harm',0,1,.2)
        old=w.x.copy();w.advance()
        self.assertEqual(len(w.events[0]['receipts']),2)
        self.assertEqual(len(w.events[0]['receipts'][0]['sources']),2)
        after=w.x.copy();w.advance()
        np.testing.assert_array_equal(w.x,after)
        self.assertTrue((after[:,0]<=old[:,0]+1e-10).all())

    def test_roles_isolated_vs_unassigned_and_hub(self):
        s=Simulation(7);w=s.world
        w.a=adjacency(7,[(0,1),(0,2),(1,2),(0,3),(4,5)])
        w.detector=cm.Detector();w.detector.detect(w.a)
        rows=w.role_rows()
        self.assertTrue(rows[6]['isolated'])
        self.assertTrue(rows[0]['hub'] or rows[0]['external_degree']>0)
        self.assertEqual(rows[6]['degree'],0)
        self.assertIsNone(rows[6]['community'])

    def test_degree_preserving_null(self):
        s=Simulation(20);a=s.world.a
        b,accepted=cm.rewired(a,np.random.default_rng(2))
        np.testing.assert_array_equal(a.sum(axis=1),b.sum(axis=1))
        self.assertFalse(np.diag(b).any());self.assertTrue((b==b.T).all())

    def test_export_and_boundaries(self):
        import json
        s=Simulation(12);s.act('gossip',0,1)
        for _ in range(12):s.step()
        json.dumps(s.snapshot(),allow_nan=False)
        self.assertTrue(np.isfinite(s.world.x).all())
        self.assertLessEqual(abs(s.world.x).max(),1.)
        self.assertTrue((s.world.a==s.world.a.T).all())
        with self.assertRaises(ValueError):s.act('help',0,0)


if __name__=='__main__':unittest.main()
