from bhashaflow_action import FocusSession, PointerHandoff, PointerTarget
from bhashaflow_action.targets import handoff_from_event
from bhashaflow_vision.pointer import PointerTarget as VisionPointerTarget
from bhashaflow_vision.session import VisionSession


def test_action_package_reexports_the_vision_handoff() -> None:
    assert PointerTarget is VisionPointerTarget
    session = VisionSession.for_demo_script()
    session.show("mail")
    session.tick()
    handoff = FocusSession().consume(session.ground("attach the file"))
    assert isinstance(handoff, PointerHandoff)
    assert handoff.target is not None
    assert handoff.target.action == "click"
    assert handoff.target.accessibility_id == "Mail:AXButton: Attach"
    again = handoff_from_event(session.ground("attach the file"))
    assert again.target is not None
    assert again.target.accessibility_id == handoff.target.accessibility_id
