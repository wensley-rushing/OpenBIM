from .utility import find_row

def resolve_points(csi, tags):

    if isinstance(tags, int):
        merge = find_row(csi.get("JOINT MERGE NUMBER ASSIGNMENTS",[]),
                         Joint=tags)
        if merge:
            return merge["MergeNumber"]
        else:
            return tag

    return tuple(resolve_points(csi, tag) for tag in tags)


