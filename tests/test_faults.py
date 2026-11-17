from brickts.graph.service import GraphService
from brickts.services import faults as fault_svc
from brickts.settings import Settings


def test_fault_applicability(settings: Settings):
    g = GraphService(settings)
    union = g.state.union
    rows = {r.rule_id: r for r in fault_svc.list_faults(union, "AHU_1")}
    assert rows["FC1"].applicable
    assert rows["AHU-DUCTHI"].applicable
    assert rows["FC13"].applicable
    assert not rows["FC5"].applicable
    assert not rows["FC14"].applicable
