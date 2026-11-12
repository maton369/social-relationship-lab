"""User-facing summaries preserve who acts, who hears and who is discussed."""
import unittest
from model import Simulation
from runtime import person_overview,rumor_overview


class InterfaceSummaryChecks(unittest.TestCase):
    def test_person_summary_uses_overall_incoming_evaluation(self):
        s=Simulation(8,seed=9)
        row=s.world.role_rows()[0]
        text=person_overview(s.world,row,0,1)
        self.assertIn(f'好かれ度 {row["incoming_mean"]:+.2f}',text)
        self.assertIn(f'信頼度 {row["incoming_trust"]:.2f}',text)
        self.assertNotIn('分割差VI',text)

    def test_rumor_summary_describes_the_event_not_a_new_selection(self):
        s=Simulation(8,seed=9,settings={'density':1.})
        before=rumor_overview(s.world,0,1)
        self.assertIn('人物 2',before)
        receivers=s.gossip_to_neighbors(0,1,1.)
        self.assertNotIn(1,receivers)
        self.assertFalse(s.world.events[-1]['seen'][1])
        after=rumor_overview(s.world,0,6)
        self.assertIn('人物 2の悪い評判',after)
        self.assertIn(f'知った人 {len(receivers)}人',after)
        self.assertIn('真偽は扱いません',after)


if __name__=='__main__':unittest.main()
