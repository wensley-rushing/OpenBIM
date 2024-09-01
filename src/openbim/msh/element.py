# Set of helper functions to interface gmsh with opensees 
#
# Questions to jaabell@uandes.cl
#
# 2022 - Jose A. Abell M. - www.joseabell.com


import numpy as np
import opensees.openseespy as ops

from .utils import get_physical_groups_map
from .nodes import get_all_nodes


def duplicate_equaldof_and_beam_link(ops, free_node, constrained_nodes, gmshmodel, start_duplicate_tag, start_beam_tag, transfTag, E_mod):
    """
    This is the magic function that is used to interface the continuum domain with a MoM-based domain in OpenSees
    This is similar to STKO beam-to-solid coupling, but not as refined. 
    This is a penalty approach to this problem. Very sensitive to your selection of E_mod
    """

    parent_coord, _, _, _ = gmshmodel.mesh.get_node(free_node)

    #Flatten the nodeTags array and remove duplicate nodes
    constrained_nodes = np.unique(np.array(constrained_nodes).reshape(-1))
    
    # Penalty beam properties
    Area = 1.0
    G_mod = 1.0
    Jxx = 1.0
    Iy = 1.0
    Iz = 1.0
    #Identify DOFs to be fixed
    for i, nodeTag in enumerate(constrained_nodes):
        coord, _, _, _ = gmshmodel.mesh.get_node(nodeTag)

        if np.linalg.norm(parent_coord - coord) < 1e-4:
            continue

        duplicate_tag = int(start_duplicate_tag+nodeTag)
        ops.node(duplicate_tag, *coord)
        ops.equalDOF(int(nodeTag), duplicate_tag, 1,2,3)
        # ops.rigidLink("beam", free_node, duplicate_tag)
        eleTag = start_beam_tag + i
        ops.element('elasticBeamColumn', eleTag, free_node, duplicate_tag, Area, E_mod, G_mod, Jxx, Iy, Iz, transfTag)




def get_elements_and_nodes_in_physical_group(groupname, gmshmodel):
    """
    Returns element tags, node tags (connectivity), element name (gmsh element type name), and
    number of nodes for the element type, given the name of a physical group. Inputs are the physical
    group string name and the gmsh model 
    """


    dim, tag  = get_physical_groups_map(gmshmodel)[groupname]  
    entities  = gmshmodel.getEntitiesForPhysicalGroup(dim, tag)


    allelementtags = np.array([], dtype=np.int32)
    allnodetags = np.array([], dtype=np.int32)

    base_element_type = -1

    for i,e in enumerate(entities):
        elementTypes, elementTags, nodeags = gmshmodel.mesh.getElements(dim, e)

        if len(elementTypes) == 0:
            raise ValueError("Physical group has no elements! (Mesh empty, try meshing beforehand.) ")

        if len(elementTypes) != 1:
            raise ValueError("Cannot handle more than one element type at this moment. Contributions welcome. ")

        if base_element_type == -1:
            base_element_type = elementTypes[0]

        elif elementTypes[0] != base_element_type:
            raise ValueError("All entities of physical group should have the same element type. Contributions welcome. ")


        allelementtags = np.concatenate((allelementtags, elementTags[0]))
        allnodetags = np.concatenate((allnodetags,nodeags[0]))

    element_name, element_nnodes = get_element_info_from_elementType(base_element_type)
    allnodetags = allnodetags.reshape((-1,element_nnodes))

        
    return (np.int32(allelementtags).tolist(), 
            np.int32(allnodetags).tolist(), 
            element_name, 
            element_nnodes)


def get_element_info_from_elementType(elementType):
    """
    Returns element gmsh name and number of nodes given element type
    Can be extended to add other elements.
    """
    info = {
    #  elementType    Name                  Number of nodes
        1         : ( "2-node-line"         , 2       )  ,
        2         : ( "3-node-triangle"     , 3       )  ,
        3         : ( "4-node-quadrangle"   , 4       )  ,
        4         : ( "4-node-tetrahedron"  , 4       )  ,
        5         : ( "8-node-hexahedron"   , 8       )  ,
        9         : ( "6-node-triangle"     , 6       ) ,
        11        : ( "10-node-tetrahedron" , 10      ) ,
        15        : ( "1-node-point"        , 1       )  ,
    }
    return info[elementType]

