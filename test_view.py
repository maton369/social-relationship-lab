from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
import numpy as np
from model import Simulation
from view import View


class CenteredLayoutChecks(unittest.TestCase):
    def test_selected_person_stays_at_center_while_others_move(self):
        sim = Simulation(12, seed=8)
        view = View(sim.n, sim.seed)
        actor = 6
        initial = view.pos.copy()
        state_x, state_a = sim.world.x.copy(), sim.world.a.copy()
        center = np.array([view.w / 2, (view.h - 45) / 2])
        for _ in range(80):
            view.layout(sim, pinned=actor)
        np.testing.assert_array_equal(view.pos[actor], center)
        self.assertTrue(np.any(np.linalg.norm(view.pos[np.arange(sim.n) != actor] - initial[np.arange(sim.n) != actor], axis=1) > 0))
        np.testing.assert_array_equal(sim.world.x, state_x)
        np.testing.assert_array_equal(sim.world.a, state_a)

    def test_fisheye_expands_nearby_nodes_without_moving_canvas_edge(self):
        view = View(3, seed=4, width=400, height=300)
        center = np.array([200., 127.5])
        points = np.array([center, center + [30., 0.], center + [170., 0.]])
        warped = view.fisheye(points, center, pinned=0)
        self.assertGreater(np.linalg.norm(warped[1] - center), 30.)
        self.assertAlmostEqual(np.linalg.norm(warped[2] - center), 170.)
        np.testing.assert_array_equal(warped[0], center)

    def test_other_selected_person_can_be_centered(self):
        sim = Simulation(8, seed=9)
        view = View(sim.n, sim.seed)
        for actor in (0, 3, 7):
            view.layout(sim, pinned=actor)
            np.testing.assert_array_equal(view.pos[actor], [view.w / 2, (view.h - 45) / 2])


if __name__ == '__main__':
    unittest.main()
