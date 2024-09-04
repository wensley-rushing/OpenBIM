import sees.reader.csi as csi


def make_schema(table, name):
    from genson import SchemaBuilder

    builder = SchemaBuilder()
    builder.add_schema({"type": "object", "properties": {}, "name": name})

    for row in table:
        builder.add_object(row)

    return builder.to_schema()



if __name__ == "__main__":
    import sys
    import json

    tables = {}
    for file in sys.argv[1:]:
        print(file, file=sys.stderr)
        with open(file, "r") as f:
            csi.load(f, append=tables)


#   print(json.dumps(tables))

    print(json.dumps({key: print(key, file=sys.stderr) or make_schema(row, key)
          for key, row in tables.items()}))


