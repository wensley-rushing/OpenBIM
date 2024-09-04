from openbim.csi import create_model, load 

if __name__ == "__main__":
    import sys
    import sees

    with open(sys.argv[1], "r") as f:
        sap = load(f)

    sees.serve(sees.render(create_model(sap, verbose=True), canvas="gltf"))

