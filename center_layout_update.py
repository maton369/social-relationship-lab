"""Apply the center-pinned view to the already-open analysis component.
Run once in the existing TouchDesigner Textport; this does not reset the simulation.
"""
from pathlib import Path
import json
import numpy as np
import td

COMP = td.op('/social_relationship_lab_v2_analysis')
if COMP is None:
    raise RuntimeError('Open the project containing /social_relationship_lab_v2_analysis first.')
BASE = Path(str(COMP.par.Basefolder)).expanduser()
if not (BASE / 'view.py').is_file():
    raise RuntimeError('Basefolder must point to the cloned v2 project folder containing view.py: ' + str(BASE))
was_running = bool(COMP.par.Running)
COMP.par.Running = False
COMP.par.bgcolorr = .047
COMP.par.bgcolorg = .078
COMP.par.bgcolorb = .122
COMP.par.bgalpha = 1
old_runtime = COMP.op('runtime').module
simulation = old_runtime.sim
# Replace the embedded source and reload it before constructing View. The old
# module may not accept the `pinned` keyword used by the current layout API.
COMP.op('view').text = (BASE / 'view.py').read_text(encoding='utf-8')
COMP.op('runtime').text = (BASE / 'runtime.py').read_text(encoding='utf-8')
view_module = COMP.op('view').module
view = view_module.View(simulation.n, simulation.seed)
actor = int(COMP.par.Actor) - 1
for _ in range(100):
    view.layout(simulation, pinned=actor)
runtime = COMP.op('runtime').module
runtime.sim = simulation
runtime.view = view
runtime.last_tick = 0.
runtime.refresh()
expected = np.array([view.w / 2, (view.h - 45) / 2])
if not np.allclose(view.pos[actor], expected):
    raise RuntimeError('Selected person was not centered.')
COMP.par.Running = was_running
runtime.refresh()
COMP.op('panel_capture').cook(force=True)
COMP.op('panel_capture').save(str(BASE / 'docs/screenshots/centered_network.png'))
COMP.save(str(BASE / 'Social_Relationship_Lab_Analysis.tox'))
(BASE / 'center_layout_validation.json').write_text(json.dumps({
    'ok': True, 'actor': actor + 1, 'position': view.pos[actor].tolist(),
    'center': expected.tolist(), 'step': simulation.iteration,
    'project': td.project.name, 'toe_saved': False,
}, ensure_ascii=False, indent=2), encoding='utf-8')
