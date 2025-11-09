from albion.torch import Torch
from albion.torch.types import Executable, Method, TypeReference, WildcardKind, AccessModifier

from . import RosettaMethod, RosettaContext, RosettaExecutable


def compare_type(torch_type: TypeReference, rosetta_type: TypeReference, full: bool) -> bool:
    if torch_type.array_dimensions != rosetta_type.array_dimensions:
        return False

    if full:
        if (torch_type.package != rosetta_type.package
                or len(torch_type.elements) != len(rosetta_type.elements)):
            return False
        rosetta_elements = rosetta_type.elements
    else:
        rosetta_elements = list(rosetta_type.elements)
        if len(rosetta_type.elements) > len(torch_type.elements):
            package_elements = torch_type.package.split("/")
            if len(rosetta_type.elements) != len(torch_type.elements) + len(package_elements):
                return False
            for i, element in enumerate(package_elements):
                if element != rosetta_elements[i].name:
                    return False
            rosetta_elements = rosetta_elements[len(package_elements):]

    # we loop through these reversed because if the rosetta one is shorter, we only want to check the last ones
    reversed_elements = list(reversed(torch_type.elements))
    for i, element in enumerate(reversed(rosetta_elements)):
        torch_element = reversed_elements[i]

        if element.name != torch_element.name:
            return False

        if full:
            if len(element.type_arguments) != len(torch_element.type_arguments):
                return False

            for j, type_argument in enumerate(element.type_arguments):
                torch_argument = torch_element.type_arguments[j]

                if torch_argument.wildcard_kind is not type_argument.wildcard_kind:
                    return False

                if torch_argument.wildcard_kind is not WildcardKind.UNBOUNDED and not compare_type(torch_argument.type, type_argument.type, full):
                    return False

    return True


def find_cluster_matches(cluster: list[Executable], rosetta: list[RosettaExecutable], class_name: str):
    for executable in cluster:
        doc_methods = [
            doc for doc in rosetta if len(doc.parameter_types) == len(executable.parameters)
        ]

        # bleugh...
        if isinstance(executable, Method):
            for doc in reversed(doc_methods):
                assert isinstance(doc, RosettaMethod)
                if not executable.static == doc.static \
                        or not compare_type(executable.returns, doc.return_type.type, doc.return_type.full):
                    doc_methods.remove(doc)

        for i, parameter in enumerate(executable.parameters):
            for doc in reversed(doc_methods):
                _type = doc.parameter_types[i]
                if not compare_type(parameter, _type.type, _type.full):
                    doc_methods.remove(doc)

            if len(doc_methods) < 1:
                break

        if len(doc_methods) < 1:
            if not executable.access_modifier > AccessModifier.PROTECTED:
                print(f"Rosetta: No documentation found for {class_name}#{repr(executable)}")
        else:
            if len(doc_methods) > 1:
                print(f"Rosetta: WEIRD: found multiple valid documentations for {class_name}#{repr(executable)}")
                for rosetta_method in doc_methods[1:]:
                    rosetta.remove(rosetta_method)

            rosetta_method = doc_methods[0]
            executable.docs = rosetta_method.docs
            rosetta.remove(rosetta_method)

    for rosetta_method in rosetta:
        print(f"Rosetta: Documented method {class_name}#{repr(rosetta_method)} does not exist")


def apply_rosetta(torch: Torch, rosetta: RosettaContext) -> None:
    for package, classes in rosetta.items():
        package = package.replace(".", "/")
        if package not in torch.packages:
            print(f"Rosetta: Rosetta documentation exists for unknown package {package}")
            continue

        torch_package = torch.packages[package]
        for name, clazz in classes.items():
            full_name = package + "/" + name
            if name not in torch_package.classes:
                # print(f"Rosetta: Rosetta documentation exists for unknown class {full_name}")
                continue

            torch_clazz = torch_package.classes[name]
            torch_clazz.docs = clazz.docs

            for method_name, cluster in clazz.methods.items():
                if method_name in torch_clazz.methods:
                    find_cluster_matches(torch_clazz.methods[method_name].methods, cluster, full_name)
                else:
                    print(f"Rosetta: Documented method {full_name}#{method_name} does not exist")

            undocumented_clusters = [
                cluster for cluster in torch_clazz.methods.values() if cluster.name not in clazz.methods.keys()
            ]

            for cluster in undocumented_clusters:
                is_visible = False
                for method in cluster.methods:
                    if method.access_modifier <= AccessModifier.PROTECTED:
                        is_visible = True
                        break
                if is_visible:
                    print(f"Rosetta: No documentation for cluster {cluster.name} in class {full_name}")

            for field_name, field in clazz.fields.items():
                if field_name in torch_clazz.fields:
                    torch_field = torch_clazz.fields[field_name]
                    if field.static != torch_field.static:
                        print(f"Rosetta: Field {full_name}#{field_name} does not match")
                    else:
                        torch_field.docs = field.docs
                else:
                    print(f"Rosetta: Documented field {full_name}#{field_name} does not exist")

            if len(clazz.constructors) > 0:
                find_cluster_matches(torch_clazz.constructors, clazz.constructors, full_name)

        for clazz in torch_package.classes.values():
            if clazz.simple_name() not in classes.keys() and clazz.access_modifier is AccessModifier.PUBLIC:
                print(f"Rosetta: No documentation exists for class {clazz.name}")
