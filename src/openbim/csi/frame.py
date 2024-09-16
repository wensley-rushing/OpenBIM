import sys
import numpy as np

from .utility import UnimplementedInstance, find_row, find_rows

def _orient(xi, xj, angle):
    """
    Calculate the coordinate transformation vector.
    xi is the location of node I, xj node J,
    and `angle` is the rotation about the local axis

    By default local axis 2 is always in the 1-Z plane, except if the object
    is vertical and then it is parallel to the global X axis.
    The definition of the local axes follows the right-hand rule.
    """

    # The local 1 axis points from node I to node J
    d_x, d_y, d_z = e_x = xj - xi
    # Global z
    g_z = np.array([0, 0, 1])

    # In Sap2000, if the element is vertical, the local y-axis is the same as the
    # global x-axis, and the local z-axis can be obtained by cross-multiplying
    # the local x-axis with the local y-axis.
    if d_x == 0 and d_y == 0:
        l_y = np.array([1, 0, 0])
        l_z = np.cross(e_x, l_y)

    # In other cases, the plane composed of the local x-axis and the local
    # y-axis is a vertical plane (that is, the normal vector level). In this
    # case, the local z-axis can be obtained by the cross product of the local
    # x-axis and the global z-axis.
    else:
        l_z = np.cross(e_x, g_z)

    # Rotate the local axis using the Rodrigue rotation formula
    l_z_rot = l_z * np.cos(angle / 180 * np.pi) + np.cross(e_x, l_z) * np.sin(angle / 180 * np.pi)
    # Finally, the normalized local z-axis is returned
    return l_z_rot / np.linalg.norm(l_z_rot)



def _is_truss(frame, csi):
    if "FRAME RELEASE ASSIGNMENTS 1 - GENERAL" in csi:
        release = find_row(csi["FRAME RELEASE ASSIGNMENTS 1 - GENERAL"],
                        Frame=frame["Frame"])
    else:
        return False

    return release and all(release[i] for i in ("TI", "M2I", "M3I", "M2J", "M3J"))


def create_frames(sap, model, library, config):
    ndm = 3
    log = []

    itag = 1
    transform = 1

    for frame in sap.get("CONNECTIVITY - FRAME",[]):
        if _is_truss(frame, sap):
            log.append(UnimplementedInstance("Truss", frame))
            continue

        if "IsCurved" in frame and frame["IsCurved"]:
            log.append(UnimplementedInstance("Frame.Curve", frame))



        nodes = (frame["JointI"], frame["JointJ"])

        if "FRAME ADDED MASS ASSIGNMENTS" in sap:
            row = find_row(sap["FRAME ADDED MASS ASSIGNMENTS"],
                            Frame=frame["Frame"])
            mass = row["MassPerLen"] if row else 0.0
        else:
            mass = 0.0
        
        # Geometric transformation
        if "FRAME LOCAL AXES ASSIGNMENTS 1 - TYPICAL" in sap:
            row = find_row(sap["FRAME LOCAL AXES ASSIGNMENTS 1 - TYPICAL"],
                            Frame=frame["Frame"])
            angle = row["Angle"] if row else 0.0
        else:
            angle = 0
            
        xi = np.array(model.nodeCoord(nodes[0]))
        xj = np.array(model.nodeCoord(nodes[1]))
        if np.linalg.norm(xj - xi) <= 1e-8:
            print(f"ZERO LENGTH FRAME: {frame['Frame']}")
            continue

        if ndm == 3:
            vecxz = _orient(xi, xj, angle)
            model.geomTransf("Linear", transform, *vecxz)
        else:
            model.geomTransf("Linear", transform)

        transform += 1


        # Find section
        assign  = find_row(sap["FRAME SECTION ASSIGNMENTS"],
                           Frame=frame["Frame"])

        section = library["frame_sections"][assign["AnalSect"]]

        if len(section.integration) == 1:
            model.element("PrismFrame", None,
                          nodes,
                          section=section.index,
                          transform=transform-1,
                          mass=mass
            )


        else:
            model.beamIntegration("UserDefined",
                                  itag,
                                  len(section.integration),
                                  tuple(i[0] for i in section.integration),
                                  tuple(i[1] for i in section.integration),
                                  tuple(i[2] for i in section.integration))

            model.element("ForceFrame", None,
                          nodes,
                          transform-1,
                          itag,
                          mass=mass
            )

            itag += 1

    return log

