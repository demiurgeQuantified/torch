from operator import attrgetter
from typing import Any
from pathlib import Path

from albion.torch import ClassType
from albion.torch.types import Class, Field, Method, Constructor, InheritanceModifier, Type
from albion.torch.docs import DocNode, Deprecable

import yaml
from yamlcore import CoreDumper


def format_full_type(type: ClassType) -> str:
    return str(type).replace(".", "$").replace("/", ".")


def apply_docs(obj: dict[str, Any], docs: DocNode):
    if docs.notes != "":
        obj["notes"] = docs.notes

    if isinstance(docs, Deprecable):
        # TODO: write this if we have a @Deprecated annotation too
        if docs.deprecated:
            obj["deprecated"] = True


def write_type(type: Type) -> dict[str, Any]:
    return {
        "basic": type.simple_name().split("<", 1)[0],
        "full": format_full_type(type)
    }


def write_field(field: Field) -> dict[str, Any]:
    obj = {
        "name": field.name,
        "modifiers": [
            field.access_modifier.name.lower(),
        ],
        "type": write_type(field.type)
    }

    if field.static:
        obj["modifiers"].append("static")

    if field.docs is not None:
        apply_docs(obj, field.docs)

    return obj


def write_parameters(obj: dict[str, Any], executable: Method | Constructor) -> None:
    if len(executable.parameters) < 1:
        return

    obj["parameters"] = [
        {
            "name": parameter.name,
            "type": write_type(parameter.type),
        } for i, parameter in enumerate(executable.parameters)
    ]

    for i, parameter in enumerate(executable.parameters):
        if parameter.notes != "":
            obj["parameters"][i]["notes"] = parameter.notes

        if parameter.nullable is not None:
            obj["parameters"][i]["nullable"] = parameter.nullable


def write_method(method: Method) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "name": method.name,
        "modifiers": [
            method.access_modifier.name.lower()
        ]
    }

    if method.inheritance_modifier is not InheritanceModifier.NONE:
        obj["modifiers"].append(method.inheritance_modifier.name.lower())

    if method.static:
        obj["modifiers"].append("static")

    write_parameters(obj, method)

    obj["return"] = {
        "type": write_type(method.returns.type)
    }

    if method.returns.name != "":
        obj["return"]["name"] = method.returns.name

    if method.returns.notes != "":
        obj["return"]["notes"] = method.returns.notes

    if method.returns.nullable is not None:
        obj["return"]["type"]["nullable"] = method.returns.nullable

    if method.docs is not None:
        apply_docs(obj, method.docs)

    return obj


def write_constructor(constructor: Constructor) -> dict[str, Any]:
    obj = {
        "modifiers": [
            constructor.access_modifier.name.lower()
        ]
    }

    write_parameters(obj, constructor)

    if constructor.docs is not None:
        apply_docs(obj, constructor.docs)

    return obj


def write_class(clazz: Class) -> dict[str, Any]:
    obj: dict[str, Any] = {}

    if clazz.super is not None:
        obj["extends"] = format_full_type(clazz.super)

    obj["modifiers"] = [
        clazz.access_modifier.name.lower()
    ]
    if clazz.inheritance_modifier is not InheritanceModifier.NONE:
        obj["modifiers"].append(clazz.inheritance_modifier.name.lower())
    # TODO: we can't write javaType because we don't store that

    if clazz.docs is not None:
        apply_docs(obj, clazz.docs)

    fields = {}
    static_fields = {}

    for field in sorted(clazz.fields.values(), key=attrgetter("name")):
        if field.static:
            static_fields[field.name] = write_field(field)
        else:
            fields[field.name] = write_field(field)

    if len(fields) > 0:
        obj["fields"] = fields

    if len(static_fields) > 0:
        obj["staticFields"] = static_fields

    if len(clazz.constructors) > 0:
        obj["constructors"] = [
            write_constructor(constructor) for constructor in clazz.constructors
        ]

    methods = []
    static_methods = []

    for cluster in sorted(clazz.methods.values(), key=attrgetter("name")):
        for method in cluster.methods:
            if method.static:
                static_methods.append(write_method(method))
            else:
                methods.append(write_method(method))

    if len(methods) > 0:
        obj["methods"] = methods

    if len(static_methods) > 0:
        obj["staticMethods"] = static_methods

    return obj


def write_file(classes: list[Class]) -> dict[str, Any]:
    classes_by_package: dict[str, list[Class]] = {}

    for clazz in classes:
        package = clazz.package()
        if package not in classes_by_package:
            classes_by_package[package] = []
        classes_by_package[package].append(clazz)

    return {
        "version": "1.1",
        "languages": {
            "java": {
                "packages": {
                    package_name.replace("/", "."): {
                        clazz.simple_name(): write_class(clazz) for clazz in sorted(classes, key=attrgetter("name"))
                    } for package_name, classes in classes_by_package.items()
                }
            }
        }
    }


def write_to(classes: list[Class], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        yaml.dump(write_file(classes), file, CoreDumper, sort_keys=False)
