from pathlib import Path
from typing import Any
from collections.abc import Iterable

import kirjava
import kirjava.types
from kirjava import ClassFile
from kirjava.classfile.attributes.shared import Annotations

from albion.torch.types import Class, Method, Constructor, Field, AccessModifier, TypeReference, TypeElement, \
    Annotation, InheritanceModifier, Parameter, Return

from .signature import parse_class_signature, parse_method_signature, parse_type_signature


ACC_PRIVATE = 0x0002
ACC_PROTECTED = 0x0004


def parse_element(element: Annotations.Element) -> Any:
    if isinstance(element.value, Iterable):
        return [value.value for value in element.value]

    if element.tag == b'Z':
        return element.value.value == 1

    return element.value.value


def split_package_class_elements(typename: str) -> tuple[str, list[TypeElement]]:
    package_end = typename.rfind("/")

    if package_end == -1:
        package = ""
    else:
        package = typename[:package_end]
        typename = typename[package_end + 1:]

    return package, [TypeElement(class_name) for class_name in typename.split(".")]


def parse_type_reference(type: kirjava.types.Type) -> TypeReference:
    if isinstance(type, kirjava.types.Array):
        return TypeReference(
            *split_package_class_elements(type.lowest_element.name.replace("$", ".")),
            array_dimensions=type.dimensions
        )
    return TypeReference(
        *split_package_class_elements(type.name.replace("$", "."))
    )


def create_annotations(annotations: Annotations) -> list[Annotation]:
    torch_annotations: list[Annotation] = []

    if annotations is not None:
        for annotation in annotations:
            torch_annotations.append(
                Annotation(
                    type=parse_type_signature(annotation.descriptor.value),
                    arguments={element[0].value: parse_element(element[1]) for element in annotation.elements}
                )
            )

    return torch_annotations


def create_fields(clazz: ClassFile) -> dict[str, Field]:
    fields: dict[str, Field] = {}

    for field in clazz.fields:
        if field.is_public:
            access_modifier = AccessModifier.PUBLIC
        elif field.is_protected:
            access_modifier = AccessModifier.PROTECTED
        elif field.is_private:
            access_modifier = AccessModifier.PRIVATE
        else:
            access_modifier = AccessModifier.PACKAGE

        if field.signature is not None:
            _type = parse_type_signature(field.signature.signature.value)
        else:
            _type = parse_type_reference(field.type)

        torch_field = Field(
            name=field.name,
            type=_type,
            static=field.is_static,
            access_modifier=access_modifier,
        )

        fields[torch_field.name] = torch_field

        if field.runtime_visible_annotations is not None:
            torch_field.annotations = create_annotations(field.runtime_visible_annotations)

    return fields


def create_methods(clazz: ClassFile, torch_class: Class) -> None:
    for method in clazz.methods:
        if method.name == "<clinit>":
            continue

        if method.is_public:
            access_modifier = AccessModifier.PUBLIC
        elif method.is_protected:
            access_modifier = AccessModifier.PROTECTED
        elif method.is_private:
            access_modifier = AccessModifier.PRIVATE
        else:
            access_modifier = AccessModifier.PACKAGE

        if method.name == "<init>":
            executable = Constructor(
                access_modifier=access_modifier
            )
            torch_class.constructors.append(executable)
        else:
            if method.is_final:
                inheritance_modifier = InheritanceModifier.FINAL
            elif method.is_abstract:
                inheritance_modifier = InheritanceModifier.ABSTRACT
            else:
                inheritance_modifier = InheritanceModifier.NONE

            executable = Method(
                name=method.name,
                returns=Return(type=parse_type_reference(method.return_type)),
                static=method.is_static,
                access_modifier=access_modifier,
                inheritance_modifier=inheritance_modifier
            )
            torch_class.add_method(executable)

        if method.signature is not None:
            # kirjava only saves signatures for methods that involve generics (not just generic methods)
            # parsing them is much more complex, but kirjava doesn't store the generics itself
            # so we only parse the signature if available
            parameters, returns, type_parameters = parse_method_signature(method.signature.signature.value)
            executable.parameters = [
                Parameter(type=parameter) for parameter in parameters
            ]
            if isinstance(executable, Method):
                executable.returns = Return(type=returns)
            executable.type_parameters = type_parameters
        else:
            for parameter_type in method.argument_types:
                executable.parameters.append(
                    Parameter(type=parse_type_reference(parameter_type))
                )

        has_this = isinstance(executable, Method) and not executable.static

        if method.code is not None and method.code.local_variable_table is not None \
                and len(method.code.local_variable_table) \
                >= len(executable.parameters) + (1 if has_this else 0):
            for i, parameter in enumerate(executable.parameters):
                if has_this:
                    # skip over this
                    i += 1
                parameter.name = method.code.local_variable_table[i].name.value

        if method.runtime_visible_annotations is not None:
            executable.annotations = create_annotations(method.runtime_visible_annotations)


def create_class(path: Path) -> Class:
    with path.open('rb') as file:
        clazz = kirjava.load(file)

    if clazz.signature is not None:
        superclass, interfaces, type_parameters = parse_class_signature(clazz.signature.signature.value)
    else:
        if clazz.super_name is not None:
            superclass = TypeReference(
                *split_package_class_elements(clazz.super_name.replace("$", "."))
            )
        else:
            superclass = None
        interfaces = [
            TypeReference(*split_package_class_elements(interface.replace("$", "."))) for interface in clazz.interface_names
        ]
        type_parameters = []

    if clazz.runtime_visible_annotations is not None:
        annotations = create_annotations(clazz.runtime_visible_annotations)
    else:
        annotations = []

    if clazz.is_final:
        inheritance_modifier = InheritanceModifier.FINAL
    elif clazz.is_abstract:
        inheritance_modifier = InheritanceModifier.ABSTRACT
    else:
        inheritance_modifier = InheritanceModifier.NONE

    if clazz.access_flags & ClassFile.ACC_PUBLIC:
        access_modifier = AccessModifier.PUBLIC
    elif clazz.access_flags & ACC_PROTECTED:
        access_modifier = AccessModifier.PROTECTED
    elif clazz.access_flags & ACC_PRIVATE:
        access_modifier = AccessModifier.PRIVATE
    else:
        access_modifier = AccessModifier.PACKAGE

    torch_class = Class(
        name=clazz.name.replace("$", "."),
        super=superclass,
        implements=interfaces,
        access_modifier=access_modifier,
        inheritance_modifier=inheritance_modifier,
        type_parameters=type_parameters,
        fields=create_fields(clazz),
        annotations=annotations
    )

    create_methods(clazz, torch_class)

    return torch_class
