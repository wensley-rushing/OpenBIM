
import numpy as np
from .utility import UnimplementedInstance, find_row, find_rows


def _orient(xi, xj, deg):
    # Calculate the direction vector of the link element
    # Where a is the node number of node i, b is the node number of node j, and degree is the user-specified local axis
    # ------------------------------------------------------------------------------
    d_x, d_y, d_z = e_x = xj - xi
    # d_x = float(node_lib[node_lib.index(b) + 1]) - float(node_lib[node_lib.index(a) + 1])
    # d_y = float(node_lib[node_lib.index(b) + 2]) - float(node_lib[node_lib.index(a) + 2])
    # d_z = float(node_lib[node_lib.index(b) + 3]) - float(node_lib[node_lib.index(a) + 3])

    # Local 1-axis points from node I to node J
    l_x = np.array([d_x, d_y, d_z])
    # Global z-axis
    g_z = np.array([0, 0, 1])

    # In SAP2000, if the link is vertical, the local y-axis is the same as the
    # global x-axis, and the local z-axis can be obtained by crossing the local
    # x-axis with the local y-axis
    if d_x == 0 and d_y == 0:
        l_y = np.array([1, 0, 0])
        l_z = np.cross(l_x, l_y)

    # In other cases, the plane formed by the local x-axis and the local y-axis
    # is a vertical plane (i.e., the normal vector is horizontal), and the
    # local z-axis can be obtained by crossing the local x-axis with the global
    # z-axis
    else:
        l_z = np.cross(l_x, g_z)
    # The local axis may also be rotated using the Rodrigues' rotation formula
    l_z_rot = l_z * np.cos(float(deg) / 180 * np.pi) + np.cross(l_x, l_z) * np.sin(float(deg) / 180 * np.pi)
    # The rotated local y-axis can be obtained by crossing the rotated local z-axis with the local x-axis
    l_y_rot = np.cross(l_z_rot, l_x)
    # Finally, return the normalized local y-axis
    return l_y_rot / np.linalg.norm(l_y_rot)



def create_links(csi, model, library, config):
    log = []


    # Dictionary for link local axis rotation
    link_local = {}

    for link in csi.get("CONNECTIVITY - LINK",[]):
        nodes = (link["JointI"], link["JointJ"])

        assign = find_row(csi["LINK PROPERTY ASSIGNMENTS"],
                          Link=link["Link"])

        axes   = find_row(csi.get("LINK LOCAL AXES ASSIGNMENTS 1 - TYPICAL",[]),
                          Link=link["Link"])

        if not axes or axes["AdvanceAxes"]:
            log.append(UnimplementedInstance("Link.AdvancedAxes", link))
            continue
        else:
            angle = axes["Angle"]

        props  = find_row(csi["LINK PROPERTY DEFINITIONS 01 - GENERAL"],
                          Link=assign["LinkProp"])
        
        material = library["link_materials"][assign["LinkProp"]]

        if assign["LinkType"] == "Linear":
            pass

        xi = np.array(model.nodeCoord(nodes[0]))
        xj = np.array(model.nodeCoord(nodes[1]))

        model.element("TwoNodeLink", None,
                      nodes,
                      mat=material,
                      orient=tuple(_orient(xi, xj, angle))
                      )

    return log
