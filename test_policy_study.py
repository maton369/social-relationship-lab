"""Checks for the experiment protocol, independent of the application UI."""
import unittest
import numpy as np
from experiments.run_policy_study import prepare, execute, targets, intervene
from experiments.run_social_dynamics import digest


class PolicyStudyTests(unittest.TestCase):
    def test_null_copy_and_replay(self):
        initial = prepare(3, .1, 1)
        before = digest(initial.world)
        row, sim, _ = execute(initial, 'none', 20)
        self.assertEqual(row['final_digest'], row['baseline_digest'])
        self.assertEqual(digest(initial.world), before)
        self.assertIs(sim.world.social.world, sim.world)
        row, _, actions = execute(initial, 'help_spaced', 20)
        replay, _, repeated = execute(initial, 'help_spaced', 20)
        self.assertEqual(row, replay)
        self.assertEqual(actions, repeated)
        self.assertEqual([e['step']-initial.iteration for e in actions], [0,4,8,12,16])

    def test_synthetic_trust_is_paired(self):
        for condition,value in [('low',.15),('high',.85)]:
            sim=prepare(3,.1,1,condition)
            np.testing.assert_array_equal(sim.world.social.trust,sim.base.social.trust)
            np.testing.assert_array_equal(sim.world.social.trust,sim.world.a*value)

    def test_targets_are_fixed_and_no_self_actions(self):
        sim=prepare(3,.1,1)
        selected=targets(sim.world)
        neighbors=np.flatnonzero(sim.world.a[0])
        self.assertIn(selected['weak'], neighbors)
        self.assertIn(selected['strong'], neighbors)
        self.assertNotIn(selected['new'], neighbors)
        for value in selected.values():
            if value is not None:self.assertNotEqual(value,0)
        intervene(sim,'help_weak',0,selected)
        self.assertEqual(sim.world.scheduled_actions[-1]['targets'],[selected['weak']])


if __name__=='__main__':unittest.main()
