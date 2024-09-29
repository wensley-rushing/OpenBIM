#===----------------------------------------------------------------------===#
#
#         STAIRLab -- STructural Artificial Intelligence Laboratory
#
#===----------------------------------------------------------------------===#
import meshio


def load(file):
    return meshio.read(file)


def create_model(obj, verbose=False):
    import opensees.openseespy as ops

    model = ops.Model(ndm=3, ndf=6)

    for i, point in enumerate(obj.points):
        model.node(i, tuple(point))

    # Create Materials

    E = 29e3
    nu = 0.2
    mat = 1
    model.nDMaterial("ElasticIsotropic", mat, E, nu)

    #
    # Create Elements
    #
    i = 1
    for block in obj.cells:
        if block.type == "hexahedron":
            for nodes in block.data:
                if len(nodes) == 8:
                    model.element("stdBrick", i, tuple(nodes), mat)
                    i += 1


    return model


def apply_loads():
    pass

