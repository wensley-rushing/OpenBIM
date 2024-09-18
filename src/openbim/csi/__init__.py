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
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from .parse import load
from .utility import UnimplementedInstance, find_row, find_rows, print_log
from .frame import create_frames
from .point import create_points
from .link import create_links

RE = {
    "joint_key": re.compile("Joint[0-9]")
}

CONFIG = {
    "Frame": {
        "Taper": "Subdivide", # Integrate
        "Element": "PrismFrame",
    }
}

TYPES = {
    "Shell": {
        "Elastic": "ShellMITC4",
    },
    "Frame": {
        "Elastic": "PrismFrame"
    }
}

class _Material:
    @dataclass
    class _Steel:
        Fy:    float
        Fu:    float
        EffFy: float

class _Section:
    def __init__(self, name: str, csi: dict,
                 index: int, model, library):
        self.index = index
        self.name = name
        self.integration = []

        self._create(csi, model, library, None)

    def _create(self, csi, model, library, config):
        pass


class _ShellSection(_Section):
    def _create(self, csi, model, library, config):

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
        self.integration.append(self.index)


def _create_frame_sections(csi, model, library):
    tag = 1
    for assign in csi.get("FRAME SECTION ASSIGNMENTS", []):

        if assign["AnalSect"] not in library["frame_sections"]:

            library["frame_sections"][assign["AnalSect"]] = \
              _FrameSection(assign["AnalSect"], csi, tag, model, library)

            tag += len(library["frame_sections"][assign["AnalSect"]].integration)

    return tag


class _FrameSection(_Section):
    polygon: list

    def _create(self, csi, model, library, config=None):

        self.polygon = []

        section = find_row(csi["FRAME SECTION PROPERTIES 01 - GENERAL"],
                           SectionName=self.name
        )

        segments = find_rows(csi.get("FRAME SECTION PROPERTIES 05 - NONPRISMATIC",[]),
                             SectionName=section["SectionName"])

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
                self.integration.append(self.index)


        elif section["Shape"] == "Nonprismatic" and \
             len(segments) != 1: #section["NPSecType"] == "Advanced":

            # TODO: Currently just treating advanced as normal prismatic section

            assert all(segment["StartSect"] == segment["EndSect"] for segment in segments)

            if segments[0]["StartSect"] not in library:
                library[segments[0]["StartSect"]] = \
                        _FrameSection(segments[0]["StartSect"], csi, self.index, model, library)
            self.integration.append(self.index)


        # 
        elif section["Shape"] == "Nonprismatic" and \
             len(segments) == 1: #section["NPSecType"] == "Default":

            segments = find_rows(csi["FRAME SECTION PROPERTIES 05 - NONPRISMATIC"],
                                 SectionName=section["SectionName"])

            assert len(segments) == 1
            segment = segments[0]

            # Create property interpolation
            def interpolate(point, prop):
                si = find_row(csi["FRAME SECTION PROPERTIES 01 - GENERAL"],
                                   SectionName=segment["StartSect"]
                )
                sj = find_row(csi["FRAME SECTION PROPERTIES 01 - GENERAL"],
                                   SectionName=segment["EndSect"]
                )
                # TODO: Taking material from first section assumes si and sj have the same
                # material
                material = find_row(csi["MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES"],
                                    Material=si["Material"]
                )

                if prop in material:
                    start= end = material[prop]
                else:
                    start = si[prop]
                    end = sj[prop]

                power = {
                        "Linear":    1,
                        "Parabolic": 2,
                        "Cubic":     3
                }[segment.get(f"E{prop}Var", "Linear")]

                return start*(1 + point*((end/start)**(1/power)-1))**power


            # Define a numerical integration scheme

            from numpy.polynomial.legendre import leggauss
            nip = 5
            off = 1
            for x,wi in zip(*leggauss(nip)):
                xi = (1+x)/2

                model.section("FrameElastic", self.index+off,
                              A  = interpolate(xi, "Area"),
                              Ay = interpolate(xi, "AS2"),
                              Az = interpolate(xi, "AS2"),
                              Iz = interpolate(xi, "I33"),
                              Iy = interpolate(xi, "I22"),
                              J  = interpolate(xi, "TorsConst"),
                              E  = interpolate(xi, "E1"),
                              G  = interpolate(xi, "G12")
                )


                self.integration.append((self.index+off, xi, wi/2))

                off += 1


        else:
            # TODO: truss section?
            warnings.warn(f"Unknown shape {section['Shape']}")
            pass

        # TODO
        outline = "FRAME SECTION PROPERTIES 06 - POLYGON DATA"


def create_materials(csi, model):
    library = {
      "frame_sections": {},
      "shell_sections": {},
      "link_materials": defaultdict(dict),
    }

    # 1) Material

    #
    # 2) Links
    #
    mat_total = 1

    for link in csi.get("LINK PROPERTY DEFINITIONS 02 - LINEAR", []):
        if link["Fixed"]:
            # TODO: log warning
            pass

        name = link["Link"]
        if "R" in link["DOF"]:
            stiff = link["RotKE"]
            damp  = link["RotCE"]
        else:
            stiff = link["TransKE"]
            damp  = link["TransCE"]

        # TODO: use damp
        model.eval(f"uniaxialMaterial Elastic {mat_total} {stiff}\n")

        dof = link["DOF"]
        library["link_materials"][name][dof] = mat_total
        mat_total += 1

    for damper in csi.get("LINK PROPERTY DEFINITIONS 04 - DAMPER", []):
        continue
        name = damper["Link"]
        stiff = damper["TransK"]
        dampcoeff = damper["TransC"]
        exp = damper["CExp"]
        model.eval(f"uniaxialMaterial ViscousDamper {mat_total} {stiff} {dampcoeff}' {exp}\n")

        dof = damper["DOF"]
        library["link_materials"][name][dof] = mat_total
        mat_total += 1

    for link in csi.get("LINK PROPERTY DEFINITIONS 10 - PLASTIC (WEN)", []):
        name = link["Link"]

        if not link.get("Nonlinear", False):
            stiff = link["TransKE"]
            model.eval(f"uniaxialMaterial Elastic {mat_total} {stiff}\n")
        else:
            stiff = link["TransK"]
            fy    = link["TransYield"]
            exp   = link["YieldExp"] # TODO
            ratio = link["Ratio"]
            model.eval(f"uniaxialMaterial Steel01 {mat_total} {fy} {stiff} {ratio}\n")

        dof = link["DOF"]
        library["link_materials"][name][dof] = mat_total
        mat_total += 1


    # 2) Frame
    tag = _create_frame_sections(csi, model, library)


    # 3) Shell
    for assign in csi.get("AREA SECTION ASSIGNMENTS", []):
        if assign["Section"] not in library["shell_sections"]:
            library["shell_sections"][assign["Section"]] = \
              _ShellSection(assign["Section"], csi, tag, model, library)
            tag += len(library["shell_sections"][assign["Section"]].integration)

    return library

def apply_loads(csi, model):
    "LOAD CASE DEFINITIONS",
    "LOAD PATTERN DEFINITIONS",

    "JOINT LOADS - FORCE",
    "FRAME LOADS - DISTRIBUTED",
    "FRAME LOADS - GRAVITY",
    "FRAME LOADS - POINT",
    "CABLE LOADS - DISTRIBUTED",
    pass



def create_model(sap, types=None, verbose=False):

    import opensees.openseespy as ops

    config = CONFIG

    used = {
        "TABLES AUTOMATICALLY SAVED AFTER ANALYSIS"
    }
    log = []


    #
    # Create model
    #
    dofs = {key:val for key,val in sap["ACTIVE DEGREES OF FREEDOM"][0].items() } # if val }
    dims = {key for key,val in sap["ACTIVE DEGREES OF FREEDOM"][0].items() } # if val }
    ndf = sum(1 for v in sap["ACTIVE DEGREES OF FREEDOM"][0].values())
    ndm = sum(1 for k,v in sap["ACTIVE DEGREES OF FREEDOM"][0].items()
              if k[0] == "U")

    model = ops.Model(ndm=ndm, ndf=ndf)

    used.add("ACTIVE DEGREES OF FREEDOM")

#   dofs = [f"U{i}" for i in range(1, ndm+1)]
#   if ndm == 3:
#       dofs = dofs + ["R1", "R2", "R3"]
#   else:
#       dofs = dofs + ["R3"]

    config["ndm"] = ndm
    config["ndf"] = ndf
    config["dofs"] = dofs

    #
    # Create nodes
    #
    log.extend( create_points(sap, model, None, config) )

    library = create_materials(sap, model)


    # Unimplemented objects
    for item in [
        "CONNECTIVITY - CABLE",
        "CONNECTIVITY - SOLID",
        "CONNECTIVITY - TENDON"]:
        for elem in sap.get(item, []):
            log.append(UnimplementedInstance(item, elem))

    #
    # Create Links
    #
    log.extend( create_links(sap, model, library, config) )

    #
    # Create frames
    #
    log.extend( create_frames(sap, model, library, config) )

    #
    # Create shells
    #
    for shell in sap.get("CONNECTIVITY - AREA", []):
        if "AREA ADDED MASS ASSIGNMENTS" in sap:
            row = find_row(sap["AREA ADDED MASS ASSIGNMENTS"],
                           Area=shell["Area"])
            if row:
                mass = row["MassPerArea"]
            else:
                mass = 0.0
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

        model.element(type, None,
                      nodes, section
        )

    if verbose and len(log) > 0:
        print_log(log)

    if verbose and False:
        for table in sap:
            if table not in used:
                print(f"\t{table}", file=sys.stderr)

    return model

