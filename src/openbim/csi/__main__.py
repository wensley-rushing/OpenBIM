from openbim.csi import create_model, load 

if __name__ == "__main__":
    import sys

    with open(sys.argv[2], "r") as f:
        csi = load(f)

    model = create_model(csi, verbose=True)

    if sys.argv[1] == "-C":
        # Convert
        model.print("-json")

    elif sys.argv[1] == "-V":
        # Visualize
        import sees
        sees.serve(sees.render(model, canvas="gltf"))

    elif sys.argv[1] == "-Q":
        # Quiet conversion
        pass
    else:
        raise ValueError(f"Unknown operation {sys.argv[1]}")

