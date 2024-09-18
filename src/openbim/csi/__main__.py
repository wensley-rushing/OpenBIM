from openbim.csi import create_model, apply_loads, load

if __name__ == "__main__":
    import sys



    with open(sys.argv[2], "r") as f:
        csi = load(f)


    model = create_model(csi, verbose=True)

    if sys.argv[1] == "-C":
        # Convert
        model.print("-json")

    elif sys.argv[1] == "-E":
        # Eigen
        import sees
        model.constraints("Transformation")
        model.eigen(2)
        sees.serve(sees.render_mode(model, 1, 50.0, vertical=3))

    elif sys.argv[1] == "-A":
        # Apply loads and analyze
        apply_loads(csi, model)
        model.analyze(1)

    elif sys.argv[1] == "-V":
        # Visualize
        import sees
        sees.serve(sees.render(model, canvas="plotly", vertical=3))

    elif sys.argv[1] == "-Vn":
        # Visualize
        from scipy.linalg import null_space
        model.constraints("Transformation")
        model.analysis("Static")
        K = model.getTangent().T
        v = null_space(K)[:,0] #, rcond=1e-8)
        print(v)


        u = {
            tag: [1000*v[dof-1] for dof in model.nodeDOFs(tag)]
            for tag in model.getNodeTags()
        }

        import sees
        sees.serve(sees.render(model, u, canvas="gltf", vertical=3))

    elif sys.argv[1] == "-Q":
        # Quiet conversion
        pass
    else:
        raise ValueError(f"Unknown operation {sys.argv[1]}")

