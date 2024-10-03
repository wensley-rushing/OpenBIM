
import opensees.openseespy as ops

abaqus_to_meshio_type = {
    # trusses
    "T2D2": "line",
    "T2D2H": "line",
    "T2D3": "line3",
    "T2D3H": "line3",
    "T3D2": "line",
    "T3D2H": "line",
    "T3D3": "line3",
    "T3D3H": "line3",
    # beams
    "B21": "line",
    "B21H": "line",
    "B22": "line3",
    "B22H": "line3",
    "B31": "line",
    "B31H": "line",
    "B32": "line3",
    "B32H": "line3",
    "B33": "line3",
    "B33H": "line3",
    # surfaces
    "CPS4": "quad",
    "CPS4R": "quad",
    "S4": "quad",
    "S4R": "quad",
    "S4RS": "quad",
    "S4RSW": "quad",
    "S4R5": "quad",
    "S8R": "quad8",
    "S8R5": "quad8",
    "S9R5": "quad9",
    # "QUAD": "quad",
    # "QUAD4": "quad",
    # "QUAD5": "quad5",
    # "QUAD8": "quad8",
    # "QUAD9": "quad9",
    #
    "CPS3": "triangle",
    "STRI3": "triangle",
    "S3": "triangle",
    "S3R": "triangle",
    "S3RS": "triangle",
    "R3D3": "triangle",
    # "TRI7": "triangle7",
    # 'TRISHELL': 'triangle',
    # 'TRISHELL3': 'triangle',
    # 'TRISHELL7': 'triangle',
    #
    "STRI65": "triangle6",
    # 'TRISHELL6': 'triangle6',
    # volumes
    "C3D8": "hexahedron",
    "C3D8H": "hexahedron",
    "C3D8I": "hexahedron",
    "C3D8IH": "hexahedron",
    "C3D8R": "hexahedron",
    "C3D8RH": "hexahedron",
    # "HEX9": "hexahedron9",
    "C3D20": "hexahedron20",
    "C3D20H": "hexahedron20",
    "C3D20R": "hexahedron20",
    "C3D20RH": "hexahedron20",
    # "HEX27": "hexahedron27",
    #
    "C3D4": "tetra",
    "C3D4H": "tetra4",
    # "TETRA8": "tetra8",
    "C3D10": "tetra10",
    "C3D10H": "tetra10",
    "C3D10I": "tetra10",
    "C3D10M": "tetra10",
    "C3D10MH": "tetra10",
    # "TETRA14": "tetra14",
    #
    # "PYRAMID": "pyramid",
    "C3D6": "wedge",
    "C3D15": "wedge15",
    #
    # 4-node bilinear displacement and pore pressure
    "CAX4P": "quad",
    # 6-node quadratic
    "CPE6": "triangle6",
}
meshio_to_abaqus_type = {v: k for k, v in abaqus_to_meshio_type.items()}


class Node:
    def __init__(self, keyword: str, attributes: dict=None):
        self.keyword = keyword
        self.attributes = attributes if attributes else {}
        self.children = []

    def add_child(self, child_node: 'Node'):
        self.children.append(child_node)

    def __repr__(self, level=0):
        ret = "\t" * level + repr(self.keyword) + "\n"
        for child in self.children:
            ret += child.__repr__(level + 1)
        return ret

def load(filename):

    with open(filename, 'r') as file:
        root = Node("root")
        current_node = None
        stack = [root]

        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("**"):  
                # Skip empty lines and comments
                continue

            if line.startswith("*"):  # Identify keywords
                # Split keyword and attributes
                parts = line[1:].split(",", 1)
                keyword = parts[0].strip()
                attributes = {}
                if len(parts) > 1:
                    # Process attributes
                    for attr in parts[1].split(","):
                        key_value = attr.split("=")
                        if len(key_value) == 2:
                            attributes[key_value[0].strip()] = key_value[1].strip()

                # Create a new node
                new_node = Node(keyword, attributes)
                if current_node is not None:
                    current_node.add_child(new_node)
                else:
                    root.add_child(new_node)

                # Update the current node and stack
                current_node = new_node
                stack.append(new_node)

            else:
                # If we hit a new keyword, pop back to the last known node
                while stack and line.startswith("*") is False:
                    stack.pop()
                    if stack:
                        current_node = stack[-1]

        return root


def create_opensees_model(ast):
    # Create a new model
    model = ops.Model(ndm=3, ndf=3)

    # Dictionary to map material names/IDs
    material_map = {}
    section_map = {}

    # Parse materials
    for node in ast.children:
        if node.keyword == 'Material':
            for child in node.children:
                if child.keyword == 'Elastic':
                    material_name = node.attributes.get('name')
                    properties = child.children[0].attributes.get('data').split(',')
                    E = float(properties[0])
                    nu = float(properties[1])
#                   model.uniaxialMaterial('Elastic', material_name, E)
                    model.material('ElasticIsotropic', material_name, E, nu)

                elif child.keyword == 'Plastic':
                    material_name = node.attributes.get('name')
                    properties = child.children[0].attributes.get('data').split(',')
                    E = float(properties[0])
                    yield_strength = float(properties[1])
                    model.uniaxialMaterial('Plastic', material_name, E, yield_strength)

                elif child.keyword == 'Concrete':
                    material_name = node.attributes.get('name')
                    properties = child.children[0].attributes.get('data').split(',')
                    f_c = float(properties[0])  # Compressive strength
                    f_t = float(properties[1])  # Tensile strength
                    model.uniaxialMaterial('Concrete', material_name, f_c, f_t)

                material_map[node.attributes.get('name')] = material_name

        if node.keyword == 'Section':
            section_name = node.attributes.get('name')
            material_name = node.attributes.get('material')
            thickness = node.attributes.get('thickness', None)  # Optional, for 2D elements

            # Store the section information
            section_map[section_name] = {
                'material': material_name,
                'thickness': thickness
            }

    # Create elements
    for node in ast.children:
        if node.keyword == 'Part':
            for child in node.children:
                if child.keyword == 'Node':
                    for entry in child.children:
                        node_data = entry.attributes.get('data').split(',')
                        node_id = int(node_data[0])
                        coords = list(map(float, node_data[1:]))
                        model.node(node_id, *coords)

                elif child.keyword == 'Element':
                    for entry in child.children:
                        element_data = entry.attributes.get('data').split(',')
                        element_id = int(element_data[0])
                        element_type = element_data[1]
                        connectivity = list(map(int, element_data[2:]))

                        # Extract material assignment
                        material_id = entry.attributes.get('material')  # Assume material ID is stored here

                        if element_type == 'C3D4':
                            model.element('tetrahedron', element_id, *connectivity)  # Example for tetrahedral elements

                        elif element_type == 'C0D2':  # Beam example
                            model.element('elasticBeamColumn', element_id, *connectivity)

                        elif element_type == 'C3D8':  # Hexahedral element
                            model.element('brick', element_id, *connectivity)

                        elif element_type == 'C2D4':  # 2D quadrilateral element
                            model.element('quad', element_id, *connectivity)

                        elif element_type == 'C3D10':  # Tetrahedral element with mid-side nodes
                            model.element('tetrahedron', element_id, *connectivity)  # or use specific type

                        else:
                            print(f"Warning: Unrecognized element type {element_type} for element ID {element_id}.")




        elif node.keyword == 'Boundary':
            for child in node.children:
                boundary_data = child.attributes.get('data').split(',')
                node_id = int(boundary_data[0])
                dof = list(map(int, boundary_data[1:]))
                model.fix(node_id, *dof)

        elif node.keyword == 'Load':
            for child in node.children:
                load_data = child.attributes.get('data').split(',')
                node_id = int(load_data[0])
                load_values = list(map(float, load_data[1:]))
                model.load(node_id, *load_values)



if __name__ == "__main__":
    import sys
    ast = load(sys.argv[1])

    create_opensees_model(ast)


