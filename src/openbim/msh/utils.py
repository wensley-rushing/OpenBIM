
def get_physical_groups_map(gmshmodel):
	"""
    Given the gmsh model, return a map of all defined physical groups and their
    names.

    The map will return the dimension and rag of the physical group if indexed
    by name
    """

	pg = gmshmodel.getPhysicalGroups()
	the_physical_groups_map = {}
	for dim, tag in pg:
		name = gmshmodel.getPhysicalName(dim, tag)
		the_physical_groups_map[name] = (dim, tag)

	return the_physical_groups_map
