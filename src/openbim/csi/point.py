import sys
import numpy as np

from .utility import UnimplementedInstance, find_row, find_rows

def create_points(sap, model, library, config):
    log = []
    ndm = config["ndm"]
    ndf = config["ndf"]
    dofs = config["dofs"]

    used = set()

    for node in sap["JOINT COORDINATES"]:
        model.node(node["Joint"], tuple(node[i] for i in ("XorR", "Y", "Z") if i in node))

    for node in sap.get("JOINT RESTRAINT ASSIGNMENTS", []):
        model.fix(node["Joint"], tuple(int(node[i]) for i in dofs))

#   for node in sap.get("JOINT ADDED MASS ASSIGNMENTS", []):
#       model.mass(node["Joint"], tuple(int(node[i]) for i in dofs))

    for node in sap.get("JOINT ADDED MASS BY VOLUME ASSIGNMENTS", []):
        dens = find_row(sap.get("MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES",[]),
                        Material=node["Material"])["UnitMass"]
        vols = [node[f"Vol{i+1}"] for i in range(1,ndm) if f"Vol{i+1}" in node]
        vols = vols + [0.0]*(ndf-len(vols))
        mass = tuple(vol*dens for vol in vols)
        model.mass(node["Joint"], mass)

    used.add("JOINT COORDINATES")
    used.add("JOINT RESTRAINT ASSIGNMENTS")
#   used.add("JOINT ADDED MASS ASSIGNMENTS")
    used.add("JOINT ADDED MASS BY VOLUME ASSIGNMENTS")

    if True:
        # The format of body dictionary is {'node number':'constraint name'}
        constraints = {}

        for constraint in  sap.get("JOINT CONSTRAINT ASSIGNMENTS", []):
            if "Type" in constraint and constraint["Type"] == "Body":
                # map node number to constraint
                constraints[constraint["Joint"]] = constraint["Constraint"]
            else:
                log.append(UnimplementedInstance("Joint.Constraint", constraint))

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


    used.add("JOINT CONSTRAINT ASSIGNMENTS")

    return log
