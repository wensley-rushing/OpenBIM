import sys
import ifcopenshell

import openbim.msh as g2o
import opensees.openseespy as ops 

import  export 
import meshing
import analysis



ifcFile = ifcopenshell.open(sys.argv[1])
elements = ifcFile.by_type('IfcElement')


data = export. exportProperties(ifcFile, elements)

FileName = 'Facade'
file = FileName + '.step'

stepfile = export.STEPwriter(elements, data, FileName)

MyModel = meshing.mesh_physical_groups(stepfile, data, True)


Fixed = meshing.fix_boundaries(MyModel)

Meshed = meshing.meshing(Fixed, True)


opsModel = analysis.Create4NodesTetraedron(Meshed, data)


staticAnalysis = analysis.StaticAnalysis(opsModel[0], opsModel[2], Meshed )

EigenAnalysis = analysis.EigenValue(opsModel[0], Meshed )

