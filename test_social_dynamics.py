"""Behavioral checks for optional history, budgets, and autonomous exchange."""
import unittest
import numpy as np
from model import Simulation
from social_dynamics import MODES


def fixture(**settings):
    s=Simulation(4,settings=dict(witnesses=0,pmax=0,q0=0,qtri=0,trust_decay=0,**settings))
    for w in (s.world,s.base):
        w.a[:]=False
        w.a[0,1]=w.a[1,0]=w.a[0,2]=w.a[2,0]=True
        w.x[:]=0.;w.x[w.a]=.7
        w.traits['form'][:]=.55;w.traits['cut'][:]=.25
        w.detector.detect(w.a,0,track_events=False)
    return s


class SocialDynamicsChecks(unittest.TestCase):
    def test_trust_buffers_attack_and_repeated_harm_can_still_break_tie(self):
        low,high=fixture(history_enabled=True),fixture(history_enabled=True)
        low.world.social.trust[1,0]=0.;high.world.social.trust[1,0]=.9
        low.act('harm',0,1,1.);high.act('harm',0,1,1.)
        self.assertFalse(low.world.a[0,1]);self.assertTrue(high.world.a[0,1])
        self.assertGreater(high.world.x[1,0],low.world.x[1,0])
        high.act('harm',0,1,1.);high.act('harm',0,1,1.)
        self.assertFalse(high.world.a[0,1])
        self.assertEqual(high.world.social.experiences[1,0],3)

    def test_broadcast_is_queued_then_shares_one_round_budget(self):
        s=fixture(budget_enabled=True)
        s.act_to_neighbors('help',0,1.)
        self.assertEqual(len(s.world.events),0)
        self.assertEqual(s.world.pending,1)
        s.step(enforce_limit=False)
        self.assertEqual([e['strength'] for e in s.world.events],[.5,.5])
        self.assertEqual(s.world.social.last_spent[0],1.)
        self.assertAlmostEqual(s.world.x[1,0],.95)
        self.assertAlmostEqual(s.base.x[1,0],.7)

    def test_repeated_buttons_in_same_round_cannot_overspend(self):
        s=fixture(budget_enabled=True)
        s.act_to_neighbors('help',0,1.);s.act_to_neighbors('harm',0,1.)
        s.step(enforce_limit=False)
        self.assertEqual(len(s.world.events),2)
        self.assertEqual(s.world.social.last_spent[0],1.)
        self.assertTrue(any(e['kind']=='action_without_effect' for e in s.world.timeline))

    def test_hearing_gossip_and_trusting_it_are_distinct(self):
        s=fixture(history_enabled=True)
        s.world.social.trust[1:3,0]=0.
        s.gossip_to_neighbors(0,3,1.)
        self.assertTrue(s.world.events[0]['seen'][1])
        self.assertEqual(s.world.events[0]['initial_credits']['2'],0.)
        self.assertEqual(s.world.x[1,3],0.)
        self.assertFalse(s.world.events[0]['seen'][3])

    def test_sender_subject_conflict_discounts_gossip_credit(self):
        s=fixture(history_enabled=True)
        s.world.social.trust[1,0]=.8;s.world.x[0,3]=-1.
        s.gossip_to_neighbors(0,3,1.)
        self.assertAlmostEqual(s.world.events[0]['initial_credits']['2'],.8*(1-s.p['conflict_discount']))

    def test_autonomy_is_reproducible_and_control_matches_without_intervention(self):
        a=Simulation(8,seed=42,settings=MODES['adaptive'])
        b=Simulation(8,seed=42,settings=MODES['adaptive'])
        for _ in range(25):
            a.step(enforce_limit=False);b.step(enforce_limit=False)
            for field in ('x','a'):
                np.testing.assert_array_equal(getattr(a.world,field),getattr(a.base,field))
                np.testing.assert_array_equal(getattr(a.world,field),getattr(b.world,field))
            np.testing.assert_array_equal(a.world.social.trust,a.base.social.trust)
            self.assertTrue(np.all(a.world.social.last_spent<=a.p['social_budget']+1e-9))
            self.assertTrue(np.all(a.world.social.remaining>=0))
            self.assertTrue(np.all((a.world.social.trust>=0)&(a.world.social.trust<=1)))
        self.assertTrue(any(e['kind']=='social_invitation' and e['outcome']=='accepted' for e in a.world.timeline))

    def test_intervention_and_background_share_budget(self):
        s=Simulation(8,seed=23,settings=MODES['adaptive'])
        s.act_to_neighbors('help',0,1.)
        for _ in range(10):
            s.step(enforce_limit=False)
            self.assertTrue(np.all(s.world.social.last_spent<=s.p['social_budget']+1e-9))

    def test_active_autonomy_is_not_called_absorbing(self):
        s=fixture(autonomous_enabled=True,budget_enabled=True,social_gain=0,
                  rejection_loss=0,maintenance_decay=0)
        for _ in range(20):s.step(enforce_limit=False)
        self.assertNotEqual(s.status,'absorbed')


if __name__=='__main__':unittest.main()
