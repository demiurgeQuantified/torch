from pathlib import Path
from collections.abc import Iterable

from albion.torch.types import Class, TypeReference, PRIMITIVE_TYPE_NAMES
from albion.torch.analysis.analyser import create_class

from .filesystem import FileSystem


def get_all_referenced_types(type: TypeReference) -> set[str]:
    types = set()

    if not type.is_type_variable:
        types.add(type.basic)

    for element in type.elements:
        for argument in element.type_arguments:
            if argument.type is not None:
                types |= get_all_referenced_types(argument.type)

    return types


class Package:
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.classes: dict[str, Class] = {}


class Torch:
    def __init__(self, filesystem: FileSystem) -> None:
        self.filesystem: FileSystem = filesystem
        self.packages: dict[str, Package] = {}

    def get_class(self, clazz: str) -> Class | None:
        parts = clazz.rsplit("/", 1)
        # nothing is split if the class is in the unnamed package
        if len(parts) < 2:
            package_name = ""
            clazz_name = clazz
        else:
            package_name = parts[0]
            clazz_name = parts[1]

        if package_name not in self.packages:
            return None
        package = self.packages[package_name]

        if clazz_name not in package.classes:
            return None

        return package.classes[clazz_name]

    def has_class(self, clazz: str) -> bool:
        if clazz in PRIMITIVE_TYPES:
            return True

        return self.get_class(clazz) is not None

    def get_or_create_package(self, name: str) -> Package:
        if name not in self.packages:
            # name_elements = name.split("/")
            #
            # package_name = ""
            # for element in name_elements:
            #     package_name += element
            #     if package_name not in self.packages:
            #         self.packages[package_name] = Package(package_name)
            #     package_name += "/"
            self.packages[name] = Package(name)

        return self.packages[name]

    def add_class(self, clazz: Class) -> None:
        package = self.get_or_create_package(clazz.package())
        package.classes[clazz.simple_name()] = clazz

    def get_visible_classes(self, clazz: Class) -> set[str]:
        types = set()

        for interface in clazz.get_all_supertypes():
            types |= get_all_referenced_types(interface)

        for field in clazz.fields.values():
            types |= get_all_referenced_types(field.type)

        for method in clazz.get_all_methods():
            for parameter in method.parameters:
                types |= get_all_referenced_types(parameter)
            if method.returns.basic != "void":
                types |= get_all_referenced_types(method.returns)

        for constructor in clazz.constructors:
            for parameter in constructor.parameters:
                types |= get_all_referenced_types(parameter)

        return types

    def add_class_by_path(self, clazz: Path) -> Class:
        torch_class = create_class(clazz)
        self.add_class(torch_class)
        return torch_class

    def add_classes_by_path(self, classes: Iterable[Path]) -> None:
        for clazz in classes:
            self.add_class_by_path(clazz)

    def add_class_by_name(self, clazz: str) -> Class | None:
        class_path = self.filesystem.find_class_file(clazz)
        if class_path is not None:
            return self.add_class_by_path(class_path)
        else:
            print(f"Failed to find class file for class {clazz}")
            return None

    def add_classes_by_name(self, classes: Iterable[str]) -> None:
        added_classes: list[Class] = []

        for clazz in classes:
            torch_class = self.add_class_by_name(clazz)
            if torch_class is not None:
                added_classes.append(torch_class)

    def add_class_by_name_recurse(self, clazz: str) -> None:
        self.add_classes_by_name_recurse([clazz])

    def add_classes_by_name_recurse(self, classes: Iterable[str]) -> None:
        class_stack: set[str] = set(classes)
        seen_classes: set[str] = set()

        while len(class_stack) > 0:
            clazz = class_stack.pop()
            seen_classes.add(clazz)
            if self.has_class(clazz):
                continue

            class_object = self.add_class_by_name(clazz)
            if class_object is None:
                continue

            class_stack.update(
                self.get_visible_classes(class_object)
            )
            class_stack.difference_update(seen_classes)
