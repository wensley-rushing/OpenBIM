

class _Pattern:
    @dataclass
    class JointLoad:
        joint: int
        force: list

    @dataclass
    class FrameLoad:
        pass

    def __init__(self):
        self.joint_forces = []
        self.frame_forces = []
        self.shell_forces = []

def create_loads(csi, types=None, verbose=False):
    patterns = {}
    for pattern in csi.get("LOAD PATTERN DEFINITIONS", []):
        patterns[pattern["LoadPat"]] = _Pattern()

    "FRAME LOADS - DISTRIBUTED"  # 1-001
    "FRAME LOADS - POINT"        # 1-001
    "JOINT LOADS - FORCE"



