#===----------------------------------------------------------------------===#
#
#         STAIRLab -- STructural Artificial Intelligence Laboratory
#
#===----------------------------------------------------------------------===#
#
# Certain operations are loosley adapted from:
#    https://github.com/XunXun-Zhou/Sap2OpenSees/blob/main/STO_ver1.0.py
#
import re
import sys
import warnings
from dataclasses import dataclass

import numpy as np

from .parse import load

RE = {
    "joint_key": re.compile("Joint[0-9]")
}

class UnimplementedInstance:
    def __init__(self, name, object):
        self.name = name 
        self.object = object

class _Material:
    @dataclass
    class _Steel:
        Fy:    float
        Fu:    float
        EffFy: float

class _Model:
    pass

class _Section:
    def __init__(self, name: str, csi: dict,
                 index: int, model=None):
        self.index = index
        self.name = name
        self._create(csi, model)

    def _create(self, csi, model):
        pass


class _ShellSection(_Section):
    def _create(self, csi, model, options=None):

        section = find_row(csi["AREA SECTION PROPERTIES"],
                           Section=self.name
        )
        if section is None:
            print(self.name)

        material = find_row(csi["MATERIAL PROPERTIES 01 - GENERAL"],
                            Material=section["Material"]
        )

        material = find_row(csi["MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES"],
                            Material=section["Material"]
        )
        model.section("ElasticMembranePlateSection", self.index,
                      material["E1"],  # E
                      material["G12"]/(2*material["E1"]) - 1, # nu
                      section["Thickness"],
                      material["UnitMass"]
        )

class _FrameSection(_Section):
    def _create(self, csi, model, options=None):

        section = find_row(csi["FRAME SECTION PROPERTIES 01 - GENERAL"],
                           SectionName=self.name
        )
        if section is None:
            print(csi["FRAME SECTION PROPERTIES 01 - GENERAL"])
            raise Exception(f"{self.name = }")

        if section["Shape"] not in {"Nonprismatic"}:
            material = find_row(csi["MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES"],
                                Material=section["Material"]
            )

            if "G12" in material:
                model.section("FrameElastic", self.index,
                              A  = section["Area"],
                              Ay = section["AS2"],
                              Az = section["AS2"],
                              Iz = section["I33"],
                              Iy = section["I22"],
                              J  = section["TorsConst"],
                              E  = material["E1"],
                              G  = material["G12"]
                )


        elif section["Shape"] == "Nonprismatic":
            shape = find_rows(csi["FRAME SECTION PROPERTIES 05 - NONPRISMATIC"],
                              SectionName=section["SectionName"])

        else:
            warnings.warn(f"Unknown shape {section['Shape']}")
            # TODO: truss section?
            pass

        # TODO
        outline = "FRAME SECTION PROPERTIES 06 - POLYGON DATA"



def _is_truss(frame, csi):
    if "FRAME RELEASE ASSIGNMENTS 1 - GENERAL" in csi:
        release = find_row(csi["FRAME RELEASE ASSIGNMENTS 1 - GENERAL"],
                        Frame=frame["Frame"])
    else:
        return False

    return release and all(release[i] for i in ("TI", "M2I", "M3I", "M2J", "M3J"))


def _LinkVector(xi, xj, deg):
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


def _GeomTransfVector(xi, xj, angle):
    """
    Calculate the coordinate transformation vector
    Where xi is the location of node I, xj node J,
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


def find_row(table, **kwds) -> dict:

    for row in table:
        match = True
        for k, v in kwds.items():
            if k not in row or row[k] != v:
                match = False
                break

        if match:
            return row


def find_rows(table, **kwds) -> list:
    rows = []
    for row in table:
        match = True
        for k, v in kwds.items():
            if k not in row or row[k] != v:
                match = False
                break

        if match:
            rows.append(row)

    return rows


def _create_links(csi, model):
    # Dictionary for link local axis rotation
    link_local = {}
    for line in csi.get('LINK LOCAL AXES ASSIGNMENTS 1 - TYPICAL', []):
        result = line.split()
        link = result[0].split('=')
        degree = result[1].split('=')
        link_local[link[1]] = degree[1]



def _collect_materials(csi, model):
    library = {
      "frame_sections": {},
      "shell_sections": {},
    }

    # 1) Material

    #
    # 2) Links
    #
    mat_total = 1
    for damper in csi.get("LINK PROPERTY DEFINITIONS 04 - DAMPER", []):
        continue
        name = damper["Link"]
#       dof = damper["DOF"]
        stiff = damper["TransK"]
        dampcoeff = damper["TransC"]
        exp = damper["CExp"]
        model.eval(f"uniaxialMaterial ViscousDamper {mat_total} {stiff} {dampcoeff}' {exp}\n")
        mat_total += 1

    for link in csi.get("LINK PROPERTY DEFINITIONS 10 - PLASTIC (WEN)", []):
        continue
        name = link["Link"]
        dof = link["DOF"]

        if not link["Nonlinear"]:
            stiff = link["TransKE"]
            model.eval(f"uniaxialMaterial Elastic {mat_total} {stiff}\n")
        else:
            stiff = link["TransK"]
            fy    = link["TransYield"]
            exp   = link["YieldExp"] # TODO
            ratio = link["Ratio"]
            model.eval(f"uniaxialMaterial Steel01 {mat_total} {fy} {stiff} {ratio}\n")
        mat_total += 1


    # 2) Frame
    for assign in csi.get("FRAME SECTION ASSIGNMENTS", []):
        if assign["AnalSect"] not in library["frame_sections"]:
            tag = len(library["frame_sections"])+1
            library["frame_sections"][assign["AnalSect"]] = \
              _FrameSection(assign["AnalSect"], csi, tag, model)


    # 3) Shell
    for assign in csi.get("AREA SECTION ASSIGNMENTS", []):
        if assign["Section"] not in library["shell_sections"]:
            tag = len(library["shell_sections"])+1
            library["shell_sections"][assign["Section"]] = \
              _ShellSection(assign["Section"], csi, tag, model)

    return library


def find_material(sap, cache, type, section, material):
    return 1


TYPES = {
    "Shell": {
        "Elastic": "ShellMITC4",
    },
    "Frame": {
        "Elastic": "PrismFrame"
    }
}

def create_model(sap, types=None, verbose=False):

    import opensees.openseespy as ops

    used = {
        "TABLES AUTOMATICALLY SAVED AFTER ANALYSIS"
    }
    unimpl = []

    #
    # Create model
    #
    dofs = {key for key,val in sap["ACTIVE DEGREES OF FREEDOM"][0].items() if val}
    dims = {key for key,val in sap["ACTIVE DEGREES OF FREEDOM"][0].items() if val}
    ndf = sum(int(i) for i in sap["ACTIVE DEGREES OF FREEDOM"][0].values())
    ndm = sum(int(v) for k,v in sap["ACTIVE DEGREES OF FREEDOM"][0].items()
              if k[0] == "U")
    # ndm = 3 if sap["ACTIVE DEGREES OF FREEDOM"][0]["UZ"] else 2
    # print(ndm)

    model = ops.Model(ndm=ndm, ndf=ndf)

    used.add("ACTIVE DEGREES OF FREEDOM")

    #
    # Create nodes
    #
    dofs = [f"U{i}" for i in range(1, ndm+1)]
    if ndm == 3:
        dofs = dofs + ["R1", "R2", "R3"]
    else:
        dofs = dofs + ["R3"]
    for node in sap["JOINT COORDINATES"]:
        model.node(node["Joint"], tuple(node[i] for i in ("XorR", "Y", "Z") if i in node))
    for node in sap.get("JOINT RESTRAINT ASSIGNMENTS", []):
        model.fix(node["Joint"], tuple(int(node[i]) for i in dofs))

    if True:
        # TODO
        # The format of body dictionary is {'node number':'constraint name'}
        constraints = {}

        for constraint in  sap.get("JOINT CONSTRAINT ASSIGNMENTS", []):
            # print(constraint)
            if "Type" in constraint and constraint["Type"] == "Body":
                # map node number to constraint
                constraints[constraint["Joint"]] = constraint["Constraint"]
            else:
                unimpl.append(UnimplementedInstance("Joint.Constraint", constraint))

        # Sort the dictionary by body name and return a list [(node, body name)]
        constraints = list(sorted(constraints.items(), key=lambda x: x[1]))


        if len(constraints) > 0:
            nodes = []
            # Assign the first body name to the pointer
            pointer = constraints[0][1]

            # Traverse the tuple. If the second element in the tuple, the body
            # name, is the same as the pointer, then store the node number, 
            # into nodes.
            for node, constraint in constraints:
                if constraint == pointer:
                    nodes.append(node)
                else:
                    # First write the nodes in nodes to the body file
                    for le in range(len(nodes)-1):
                        model.eval(f"rigidLink beam {nodes[0]} {nodes[le + 1]}\n")
                    # Restore nodes and save the node that returns False.
                    nodes = []
                    nodes.append(node)
                    # The pointer is changed to the new body name
                    pointer = constraint

            # After the for loop ends, write the nodes in the nodes of the last loop to the body file.
            for le in range(len(nodes)-1):
                model.eval(f"rigidLink beam {nodes[0]} {nodes[le + 1]}\n")


    used.add("JOINT COORDINATES")
    used.add("JOINT RESTRAINT ASSIGNMENTS")

    # TODO

    library = _collect_materials(sap, model)

    #
    # Create Links
    #
    # _create_links(sap, model)


    for item in [
        "CONNECTIVITY - CABLE",
        "CONNECTIVITY - LINK",
        "CONNECTIVITY - SOLID",
        "CONNECTIVITY - TENDON"]:
        for elem in sap.get(item, []):
            unimpl.append(UnimplementedInstance(item, elem))

    # Create frames
    
    transform = 1

    for frame in sap.get("CONNECTIVITY - FRAME",[]):
        if _is_truss(frame, sap):
            unimpl.append(UnimplementedInstance("Truss", frame))
            continue

        if "IsCurved" in frame and frame["IsCurved"]:
            unimpl.append(UnimplementedInstance("Frame.Curve", frame))


        type = TYPES["Frame"]["Elastic"]

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
            vecxz = _GeomTransfVector(xi, xj, angle)
            model.geomTransf("Linear", transform, *vecxz)
        else:
            model.geomTransf("Linear", transform)
        transform += 1


        # Find section
        assign  = find_row(sap["FRAME SECTION ASSIGNMENTS"],
                           Frame=frame["Frame"])

        section = library["frame_sections"][assign["AnalSect"]].index

        model.element(type, None, #frame["Frame"],
                      nodes,
                      section=section,
                      transform=transform-1,
                      mass=mass
        )

    #
    # Create shells
    #
    for shell in sap.get("CONNECTIVITY - AREA", []):
        if "AREA ADDED MASS ASSIGNMENTS" in sap:
            mass = find_row(sap["AREA ADDED MASS ASSIGNMENTS"],
                            Area=shell["Area"])["MassPerArea"]
        else:
            mass = 0.0

        # Find section
        assign  = find_row(sap["AREA SECTION ASSIGNMENTS"],
                           Area=shell["Area"])

        section = library["shell_sections"][assign["Section"]].index

        nodes = tuple(v for k,v in shell.items() if RE["joint_key"].match(k))

        if len(nodes) == 4:
            type = TYPES["Shell"]["Elastic"]

        elif len(nodes) == 3:
            type = "ShellNLDKGT"

        model.element(type, None, #shell["Area"],
                      nodes, section
        )

    if verbose:
        for item in unimpl:
            print(f"Unimplemented Feature: {item.name} - {item.object}", file=sys.stderr)

    if verbose and False:
        for table in sap:
            if table not in used:
                print(f"\t{table}", file=sys.stderr)

    return model



