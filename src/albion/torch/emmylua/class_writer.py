from operator import attrgetter

from albion.torch.types import Method, Constructor, Field, AccessModifier, Class

from . import LuaComment
from .writer import EmmyWriter


class EmmyClassWriter:
    def __init__(self, writer: EmmyWriter, clazz: Class) -> None:
        self.parent: EmmyWriter = writer
        self.clazz: Class = clazz
        self.write_supers: bool = True
        self.write_instance_members: bool = True
        self.write_static_members: bool = True
        self.min_visibility: AccessModifier = AccessModifier.PUBLIC
        self.clazz_name: str = self.parent.get_lua_name(clazz.name)
        self.identifier = self.clazz_name[self.clazz_name.rfind(".") + 1:]

    def write_function(self, name: str, parameter_names: list[str], static: bool, comment: LuaComment) -> str:
        if static:
            name = self.identifier + "." + name
        else:
            name = "__" + self.identifier + ":" + name

        string = self.parent.write_function(
            name,
            parameter_names
        )

        if not comment.is_empty():
            string = str(comment) + "\n" + string

        return string

    def write_method(self, method: Method) -> str:
        comment = self.parent.annotate_method(method)

        name = method.name
        # TODO: this logic should be moved into torchzomboid
        annotation = method.get_annotation("se/krka/kahlua/integration/annotations/LuaMethod")
        if annotation is not None:
            name = annotation.arguments.get("name", name)

        return self.write_function(
            name,
            self.parent.get_parameter_names(method),
            method.static,
            comment
        )

    def write_constructor(self, constructor: Constructor) -> str:
        comment = self.parent.annotate_type_parameters(self.clazz.type_parameters)
        comment += self.parent.annotate_executable(constructor)

        comment.add_lines("@return " + self.get_class_name())

        return self.write_function(
            "new",
            self.parent.get_parameter_names(constructor),
            True,
            comment
        )

    def write_static_field(self, field: Field) -> str:
        comment = LuaComment()
        comment += self.parent.annotate_deprecation(field)

        if field.docs is not None:
            comment.add_lines(field.docs.notes)

        comment.add_lines("@type " + self.parent.format_type_reference(field.type))

        return str(comment) + f"\n{self.identifier}.{field.name} = nil\n"

    def get_class_name(self) -> str:
        name = self.clazz_name

        type_parameters = self.clazz.type_parameters
        if len(type_parameters) > 0:
            name += f"<{", ".join(self.parent.format_type_parameter(parameter) for parameter in type_parameters)}>"

        return name

    def get_class_description(self) -> LuaComment:
        description = LuaComment()

        description += self.parent.annotate_deprecation(self.clazz)

        if self.clazz.docs is not None:
            description.add_lines(self.clazz.docs.notes)

        return description

    def get_class_declaration(self) -> LuaComment:
        class_tag = f"@class {self.get_class_name()}"

        if self.write_supers:
            supers = [
                _super for _super in self.clazz.get_all_supertypes() if _super.basic != "java/lang/Object"
            ]
            if len(supers) > 0:
                class_tag += ": " + ", ".join(self.parent.format_type_reference(_super) for _super in supers)

        declaration = LuaComment()
        declaration.add_lines(class_tag)

        return self.get_class_description() + declaration

    def write(self) -> str:
        string = str(self.get_class_declaration())
        # TODO: spamming this is ugly, write a function that adds newlines when needed
        if string != "":
            string += "\n"

        static_methods: list[Method] = []
        methods: list[Method] = []
        for cluster in sorted(self.clazz.methods.values(), key=attrgetter("name")):
            if "$" in cluster.name:
                continue

            for method in cluster.methods:
                if method.access_modifier > self.min_visibility:
                    continue

                if method.static:
                    static_methods.append(method)
                else:
                    methods.append(method)

        if self.write_instance_members:
            if string != "":
                string += "\n"
            instance_table = "__" + self.identifier
            string += f"local {instance_table} = {{}}\n"

            for method in methods:
                string += "\n" + self.write_method(method)

        if self.write_static_members:
            if string != "":
                string += "\n"

            static_table = self.identifier

            # TODO: if there are multiple classes with the same clazz_name, only the last one's static table should
            #  be rendered as global
            #  the other(s) should be local (to be exposed through package.name.clazz_name = static_table)
            string += f"{static_table} = {{}}\n"

            for field in sorted(self.clazz.fields.values(), key=attrgetter("name")):
                if not field.static or field.access_modifier > self.min_visibility or "$" in field.name:
                    continue

                string += "\n" + self.write_static_field(field)

            for method in static_methods:
                string += "\n" + self.write_method(method)

            if not self.clazz.is_abstract():
                for constructor in self.clazz.constructors:
                    if constructor.access_modifier > self.min_visibility:
                        continue
                    string += "\n" + self.write_constructor(constructor)

        return string
