import json
from string import whitespace

from typing import TypeVar
from collections.abc import Callable
from pathlib import Path

import yaml

from yamlcore import CoreLoader

from albion.torch.docs import Deprecable, Nameable, DocNode, DocExecutable, DocParameter, DocMethod, DocReturn, \
    DocClass, DocField
from albion.torch import TypeReference
from albion.torch.types import TypeElement, TypeArgument, WildcardKind

from . import RosettaType, RosettaClass, RosettaContext, RosettaMethod, RosettaField, RosettaPackage, RosettaConstructor


def read(filepath: Path, format: str) -> dict:
    if format == "yaml":
        with filepath.open("r", encoding="utf-8") as file:
            return yaml.load(file, CoreLoader)
    elif format == "json":
        with filepath.open("r", encoding="utf-8") as file:
            return json.load(file)
    else:
        raise ValueError("Unrecognised format: " + format)


def get_file_format(filepath: Path) -> str:
    if filepath.name.endswith(".yml"):
        return "yaml"
    elif filepath.name.endswith(".json"):
        return "json"
    return ""


def split_package_class_name(typename: str) -> tuple[str, str]:
    first_type_argument = typename.find("<")
    if first_type_argument == -1:
        end_pos = len(typename)
    else:
        end_pos = first_type_argument

    package_end = typename.rfind(".", 0, end_pos)

    if package_end == -1:
        package = ""
    else:
        package = typename[:package_end]
        typename = typename[package_end + 1:]

    return package, typename


def parse_type_argument(rosetta: str) -> TypeArgument:
    if rosetta.startswith("?"):
        return parse_wildcard(rosetta)

    return TypeArgument(
        type_from_rosetta(rosetta)
    )


def parse_wildcard(rosetta: str) -> TypeArgument:
    if rosetta == "?":
        return TypeArgument(
            type=TypeReference(
                "",
                elements=[TypeElement(
                    "?",
                )],
                is_type_variable=True
            ),
            wildcard_kind=WildcardKind.UNBOUNDED,
        )
    else:
        _, keyword, bound = rosetta.split(" ", 2)
        if keyword == "extends":
            kind = WildcardKind.UPPER_BOUNDED
        elif keyword == "super":
            kind = WildcardKind.LOWER_BOUNDED
        else:
            raise ValueError("Unknown wildcard kind " + keyword)

        return TypeArgument(
            type_from_rosetta(bound),
            kind
        )



def type_from_rosetta(rosetta: str) -> TypeReference:
    # bleeeurghhhhh
    array_dimensions: int = 0
    while rosetta.endswith("[]"):
        array_dimensions += 1
        rosetta = rosetta[:-2]

    package, typename = split_package_class_name(rosetta)
    package = package.replace(".", "/")

    elements: list[TypeElement] = []
    type_arguments: list[TypeArgument] = []

    argument_start: int = 0
    identifier_start: int = 0
    identifier_end: int = 0
    depth: int = 0
    i: int = 0
    while i < len(typename):
        char = typename[i]

        if char == "<":
            if depth == 0:
                argument_start = i + 1
            depth += 1
        elif char == ">":
            depth -= 1
            assert depth >= 0
            if depth == 0:
                type_arguments.append(
                    parse_type_argument(typename[argument_start:i])
                )
        elif depth == 1 and char == ",":
            assert depth > 0
            type_arguments.append(
                parse_type_argument(typename[argument_start:i])
            )
            argument_start = i + 1
        elif depth == 0:
            if char in whitespace and argument_start == i:
                argument_start = i + 1
            elif char == "$":
                elements.append(
                    TypeElement(
                        typename[identifier_start:identifier_end],
                        type_arguments
                    )
                )
                type_arguments = []
                identifier_start = i + 1
            else:
                identifier_end = i + 1

        i += 1

    assert depth == 0

    elements.append(
        TypeElement(
            typename[identifier_start:identifier_end],
            type_arguments
        )
    )

    return TypeReference(
        package,
        elements,
        array_dimensions=array_dimensions
    )


def parse_type(obj: dict) -> RosettaType:
    if "full" in obj:
        return RosettaType(
            type_from_rosetta(obj["full"]),
            True
        )

    array_dimensions = 0
    basic: str = obj["basic"]
    while basic.endswith("[]"):
        basic = basic[:-2]
        array_dimensions += 1

    return RosettaType(
        TypeReference(
            "",
            [
                TypeElement(element) for element in basic.split(".")
            ],
            array_dimensions=array_dimensions
        ),
        False,
    )


def get_parameter_types(obj: dict) -> list[RosettaType]:
    parameter_types = []
    if "parameters" in obj:
        for parameter in obj["parameters"]:
            parameter_types.append(parse_type(parameter["type"]))

    return parameter_types


def method_from_rosetta(obj: dict) -> RosettaMethod:
    return RosettaMethod(
        deserialise(DocMethod, obj),
        get_parameter_types(obj),
        parse_type(obj["return"]["type"])
    )


def constructor_from_rosetta(obj: dict) -> RosettaConstructor:
    return RosettaConstructor(
        deserialise(DocExecutable, obj),
        get_parameter_types(obj)
    )


def from_rosetta(obj: dict, context: RosettaContext | None = None) -> RosettaContext:
    if context is None:
        context = RosettaContext()

    if "languages" not in obj or "java" not in obj["languages"] or "packages" not in obj["languages"]["java"]:
        return context

    for package_name, package in obj["languages"]["java"]["packages"].items():
        if package_name in context:
            _package = context[package_name]
        else:
            _package = RosettaPackage()
            context[package_name] = _package

        for clazz_name, clazz in package.items():
            if clazz_name in _package:
                print(f"Rosetta: Duplicate definition of class {clazz_name} in package {package_name}, redefining")

            rosetta_class = RosettaClass(deserialise(DocClass, clazz))

            for method in clazz.get("methods", []):
                rosetta_method = method_from_rosetta(method)
                rosetta_class.get_methods(method["name"]).append(rosetta_method)

            for method in clazz.get("staticMethods", []):
                rosetta_method = method_from_rosetta(method)
                rosetta_method.static = True
                rosetta_class.get_methods(method["name"]).append(rosetta_method)

            for constructor in clazz.get("constructors", []):
                rosetta_class.constructors.append(
                    constructor_from_rosetta(constructor)
                )

            for field_name, field in clazz.get("fields", {}).items():
                rosetta_class.fields[field_name] = RosettaField(
                    deserialise(DocField, field),
                    static=False
                )

            for field_name, field in clazz.get("staticFields", {}).items():
                rosetta_class.fields[field_name] = RosettaField(
                    deserialise(DocField, field),
                    static=True
                )

            _package[clazz_name] = rosetta_class

    return context


def load_dir_recurse(directory: Path, context: RosettaContext | None = None) -> RosettaContext:
    if context is None:
        context = RosettaContext()

    for path, _, filenames in directory.walk():
        for filename in filenames:
            filepath = path / filename
            format = get_file_format(filepath)
            if format == "":
                continue

            obj = read(filepath, format)

            from_rosetta(obj, context)

    return context


def load_file(filepath: Path, context: RosettaContext | None = None) -> RosettaContext:
    if context is None:
        context = RosettaContext()

    assert filepath.is_file()

    format = get_file_format(filepath)

    if format == "":
        raise ValueError("Path does not point to a valid Rosetta file")

    obj = read(filepath, format)

    from_rosetta(obj, context)

    return context


T = TypeVar("T")

Deserialiser = Callable[[T, dict], None]

deserialisers: dict[type[T], Deserialiser[T]] = {}


def deserialiser[T](_type: type[T]) -> Callable[[Deserialiser[T]], Deserialiser[T]]:
    def deserialiser_impl(deserialiser: Deserialiser[T]) -> Deserialiser[T]:
        deserialisers[_type] = deserialiser
        return deserialiser

    return deserialiser_impl


def deserialise[T](_type: type[T], rosetta: dict) -> T:
    obj = _type()

    types = [_type, *_type.mro()]
    for _type in types:
        if _type in deserialisers:
            deserialisers[_type](obj, rosetta)

    return obj


@deserialiser(Deprecable)
def _(obj: Deprecable, rosetta: dict) -> None:
    obj.deprecated = rosetta.get("deprecated", False)


@deserialiser(Nameable)
def _(obj: Nameable, rosetta: dict) -> None:
    obj.name = rosetta.get("name", "")


@deserialiser(DocNode)
def _(obj: DocNode, rosetta: dict) -> None:
    obj.notes = rosetta.get("notes", "")


@deserialiser(DocExecutable)
def _(obj: DocExecutable, rosetta: dict) -> None:
    obj.parameters = [
        deserialise(DocParameter, parameter) for parameter in rosetta.get("parameters", [])
    ]


@deserialiser(DocMethod)
def _(obj: DocMethod, rosetta: dict) -> None:
    obj.returns = deserialise(DocReturn, rosetta.get("return"))
