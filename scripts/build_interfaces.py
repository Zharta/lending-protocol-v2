# ruff: noqa: T201, RUF013

from pathlib import Path

import click
from vyper import compile_code

FUNCTIONS_BLACKLIST = ["__init__", "__default__"]


def nested_get(d: dict, *args, default=None):
    if not args:
        return default
    for a in args[:-1]:
        d = d.get(a) or {}
    return d.get(args[-1], default)


def traverse_filtering(node: dict, handler: callable = None, **kwargs):
    print(kwargs, node.keys())

    def filter_keys(_node):
        return all(_node.get(k, None) == v for k, v in kwargs.items())

    yield from traverse(node, handler=handler, _filter=filter_keys)


def traverse(node: dict, handler: callable = None, _filter: callable = None):
    _handler = handler or (lambda x: x)
    if _filter is None or _filter(node):
        yield _handler(node)
    for child in node.get("body", []):
        yield from traverse(child, handler=handler, _filter=_filter)


def node_summary(node: dict):
    attrs = ["node_id", "name", "ast_type", "level", "alias", "module"]
    return ",".join(f"{attr}={node.get(attr, '')}" for attr in attrs)


def is_external_function(node):
    is_func = node["ast_type"] = "FunctionDef"
    decorators = node.get("decorator_list", [])
    return is_func and any(d for d in decorators if d["id"] == "external")


def is_public_variable(node):
    is_var = node["ast_type"] = "VariableDec"
    is_public = node.get("is_public", False)
    return is_var and is_public


def is_event(node):
    return node["ast_type"] == "EventDef"


def is_struct(node):
    return node["ast_type"] == "StructDef"


def get_arg_type(node: dict):  # noqa: PLR0911
    match node["ast_type"]:
        case "Name":
            return node["id"]
        case "Int":
            return str(node["value"])
        case "Index":
            return f"[{get_arg_type(node['value'])}]"
        case "Tuple":
            return ", ".join(get_arg_type(e) for e in node["elements"])
        case "Subscript":
            return get_arg_type(node["value"]) + get_arg_type(node["slice"])
        case "BinOp":
            return get_arg_type(node["op"])(get_arg_type(node["left"]), get_arg_type(node["right"]))
        case "Pow":
            return lambda x, y: str(int(x) ** int(y))
        case _:
            return None


def get_struct(node: dict):
    name = node.get("name")
    struct_code = [f"struct {name}:"]
    attr_list = traverse(node, _filter=lambda n: n["ast_type"] == "AnnAssign")
    attrs = [(nested_get(a, "target", "id"), get_arg_type(a["annotation"])) for a in attr_list]
    attr_code = [f"    {name}: {target}" for name, target in attrs]
    return "\n".join(struct_code + attr_code)


def get_structs(ast):
    structs = traverse(ast, _filter=is_struct)
    header = ["# Structs"]
    structs_code = [get_struct(e) for e in structs]
    return "\n\n".join(header + structs_code)


def get_event(node: dict):
    name = node.get("name")
    event_code = [f"event {name}:"]
    attr_list = traverse(node, _filter=lambda n: n["ast_type"] == "AnnAssign")
    attrs = [
        (
            nested_get(a, "target", "id"),
            get_arg_type(a["annotation"]) or nested_get(a, "annotation", "args", default=[])[0]["id"],
            nested_get(a, "annotation", "func", "id"),
        )
        for a in attr_list
    ]
    attr_code = [f"    {name}: " + (f"{func}({target})" if func else f"{target}") for name, target, func in attrs]
    return "\n".join(event_code + attr_code)


def get_events(ast):
    events = traverse(ast, _filter=is_event)
    header = ["# Events"]
    events_code = [get_event(e) for e in events]
    return "\n\n".join(header + events_code)


def get_function(node: dict):
    name = node.get("name")
    decorators = [d["id"] for d in node.get("decorator_list", [])]
    decorators_code = [f"@{d}" for d in decorators]
    arg_list = (node.get("args") or {}).get("args")
    args = [(a["arg"], get_arg_type(a.get("annotation"))) for a in arg_list]
    args_code = [f"{name}: {typ}" if typ else name for (name, typ) in args]
    return_node = node.get("returns")
    return_type = get_arg_type(return_node) if return_node else None
    return_code = f" -> {return_type}" if return_type else ""
    function_code = [f"def {name}({', '.join(args_code)}){return_code}:", "    pass"]
    return "\n".join(decorators_code + function_code)


def get_public_var(node: dict):
    name = nested_get(node, "target", "id")
    return_type = get_arg_type(node.get("annotation"))
    args = []
    if nested_get(node, "annotation", "ast_type") == "Subscript":
        annotation = node["annotation"]
        while nested_get(annotation, "value", "id") == "HashMap":
            elements = nested_get(annotation, "slice", "value", "elements")
            _args = [get_arg_type(e) for e in elements]
            return_type = _args[1]
            args.append((f"arg{len(args)}", _args[0]))
            annotation = elements[-1]

    decorators_code = ["@view", "@external"]
    args_code = [f"{name}: {typ}" for (name, typ) in args]
    return_code = f" -> {return_type}"

    function_code = [f"def {name}({', '.join(args_code)}){return_code}:", "    pass"]

    return "\n".join(decorators_code + function_code)


def get_functions(ast: dict):
    external_functions = traverse(ast, _filter=is_external_function)
    public_variables = traverse(ast, _filter=is_public_variable)
    header = ["# Functions"]
    public_vars_code = [get_public_var(v) for v in public_variables]
    functions_code = [get_function(f) for f in external_functions if f["name"] not in FUNCTIONS_BLACKLIST]
    return "\n\n".join(header + public_vars_code + functions_code)


def generate_interface(input_file: Path, output_file: Path):
    with input_file.open("r") as f:
        code = f.read()
    compiler_output = compile_code(code, ["ast_dict"])
    ast = compiler_output["ast_dict"]["ast"]

    structs = get_structs(ast)
    events = get_events(ast)
    functions = get_functions(ast)
    gen_code = "\n\n".join([structs, events, functions])  # noqa: FLY002

    with output_file.open("w") as f:
        f.write(gen_code)


@click.command()
@click.argument("filenames", nargs=-1, type=click.Path(path_type=Path, exists=True))
@click.option("-o", "--output-dir", type=click.Path(path_type=Path, exists=True), default="interfaces")
def main(filenames: list, output_dir: str):
    for f in filenames:
        opath = output_dir / f"I{f.name}"
        print(f"Generating {f} -> {opath}")
        generate_interface(f, opath)


if __name__ == "__main__":
    main()
