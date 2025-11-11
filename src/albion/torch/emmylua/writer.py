from dataclasses import dataclass, field

from albion.torch.types import TypeReference, TypeParameter, TypeArgument, WildcardKind, Executable, Method, Annotatable, \
    Documentable
from albion.torch.docs import Deprecable

from . import LuaComment, combine_strings_spaced


RESERVED_IDENTIFIERS: set[str] = {
    "and",
    "break",
    "do",
    "else",
    "elseif",
    "end",
    "false",
    "for",
    "function",
    "if",
    "in",
    "local",
    "nil",
    "not",
    "or",
    "repeat",
    "return",
    "then",
    "true",
    "until",
    "while"
}


RESERVED_TYPE_NAMES: set[str] = {
    "nil",
    "boolean",
    "number",
    "integer",
    "userdata",
    "lightuserdata",
    "thread",
    "table",
    "any",
    "void",
    "self",
    "int",
    "integer",
    "namespace",
    "function",
    "std.NotNull",
    "std.Nullable",
    "std.Select",
    "std.Unpack",
    "std.RawGet",
    "std.ConstTpl",
    "type",
    "std.type",
    "collectgarbage_opt",
    "std.collectgarbage_opt",
    "metatable",
    "std.metatable",
    "TypeGuard",
    "Language",
    "Parameters",
    "ConstructorParameters",
    "Partial",
    "bit32lib",
    "coroutinelib",
    "debuglib",
    "debuglib.DebugInfo",
    "debuglib.InfoWhat",
    "debuglib.Hookmask",
    "std.loadmode",
    "iolib",
    "iolib.OpenMode",
    "std.readmode",
    "file",
    "mathlib",
    "oslib",
    "std.osdate",
    "std.osdateparam",
    "packagelib",
    "string",
    "tablelib"
}


@dataclass
class LuaFunction:
    class Parameter:
        name: str
        type: TypeReference
        notes: str
    name: str
    has_self: bool
    parameters: list[Parameter]
    returns: Parameter | None
    comment: LuaComment
    containing_tables: list[str] = field(default_factory=list)


class EmmyWriter:
    def __init__(self) -> None:
        self.lua_name_map: dict[str, str] = {}
        """Map of class Lua names by the basic name of the same class"""

    def get_lua_name(self, basic: str) -> str:
        return self.lua_name_map.get(basic, basic)

    def format_type_argument(self, argument: TypeArgument) -> str:
        match argument.wildcard_kind:
            case WildcardKind.NONE:
                return self.format_type_reference(argument.type)
            case WildcardKind.UNBOUNDED:
                # TODO: should add ---@generic T
                return "any"
            case WildcardKind.UPPER_BOUNDED:
                # TODO: should add a ---@generic T: bound for these instead, but it's hard :(
                return self.format_type_reference(argument.type)
            case WildcardKind.LOWER_BOUNDED:
                # TODO: union of all supers
                return "any"

    def format_type_reference(self, _type: TypeReference) -> str:
        if _type.is_type_variable:
            return _type.basic
        else:
            return self.format_type(_type)

    def format_type(self, _type: TypeReference) -> str:
        name = self.get_lua_name(_type.basic)

        type_arguments = []
        for element in _type.elements:
            type_arguments += element.type_arguments

        if len(type_arguments) > 0:
            name += f"<{", ".join(self.format_type_argument(argument) for argument in type_arguments)}>"

        return name

    def format_type_parameter(self, parameter: TypeParameter) -> str:
        name = parameter.name

        bounds: list[str] = []
        for bound in parameter.bounds:
            if bound.basic == "java/lang/Object":
                continue
            bounds.append(self.format_type_reference(bound))
        if len(bounds) > 0:
            name += ": " + ", ".join(self.format_type_reference(bound) for bound in parameter.bounds)

        return name

    def write_function(self, name: str, parameters: list[str]) -> str:
        # TODO: escape reserved function names
        #  this is hard because we pass in names like 'clazz.or'
        #  so we need to check for that and do 'clazz["or"]'
        #  if it's an instance function we even have to add explicit self to the arguments :(
        string = f"function {name}({", ".join(parameters)}) end\n"

        return string

    def annotate_deprecation(self, annotatable: Annotatable) -> LuaComment:
        comment = LuaComment()

        deprecated = False
        deprecation_message = ""

        if annotatable.get_annotation("java/lang/Deprecated") is not None:
            deprecated = True
        elif (isinstance(annotatable, Documentable)
              and isinstance(annotatable.docs, Deprecable)):
            deprecated = annotatable.docs.deprecated
            deprecation_message = annotatable.docs.deprecation_message

        if deprecated:
            comment.add_lines(
                combine_strings_spaced("@deprecated", deprecation_message)
            )

        return comment

    def annotate_type_parameters(self, type_parameters: list[TypeParameter]) -> LuaComment:
        comment = LuaComment()

        for type_parameter in type_parameters:
            bounds = [bound for bound in type_parameter.bounds if bound.basic != "java/lang/Object"]
            if len(bounds) > 0:
                bounds_str = ": " + ", ".join(self.format_type_reference(bound) for bound in bounds)
            else:
                bounds_str = ""
            comment.add_lines("@generic " + type_parameter.name + bounds_str)

        return comment

    def get_parameter_names(self, executable: Executable) -> list[str]:
        if executable.docs is not None:
            parameter_names: list[str] = []
            for parameter in executable.docs.parameters:
                name = parameter.name
                if name in RESERVED_IDENTIFIERS:
                    name = "_" + name
                parameter_names.append(name)

            return parameter_names

        return ["arg" + str(i) for i in range(len(executable.parameters))]

    def annotate_parameters(self, executable: Executable) -> LuaComment:
        comment = LuaComment()

        parameter_names = self.get_parameter_names(executable)

        if executable.docs is not None:
            parameter_notes = [parameter.notes for parameter in executable.docs.parameters]
        else:
            parameter_notes = ["" for _ in executable.parameters]

        for i, parameter in enumerate(executable.parameters):
            comment.add_lines(
                combine_strings_spaced(
                    "@param", parameter_names[i], self.format_type_reference(parameter),
                    parameter_notes[i]
                )
            )

        return comment

    def annotate_executable(self, executable: Executable) -> LuaComment:
        comment = LuaComment()

        comment += self.annotate_deprecation(executable)

        if executable.docs is not None:
            comment.add_lines(executable.docs.notes)

        comment += self.annotate_type_parameters(executable.type_parameters)
        comment += self.annotate_parameters(executable)

        return comment

    def annotate_method(self, method: Method) -> LuaComment:
        comment = self.annotate_executable(method)

        if method.returns.basic != "void":
            if method.docs is not None:
                if method.docs.returns.name != "":
                    return_name = method.docs.returns.name
                else:
                    if method.docs.returns.notes != "":
                        return_name = "#"
                    else:
                        return_name = ""
                comment.add_lines(
                    combine_strings_spaced(
                        "@return",
                        self.format_type_reference(method.returns),
                        return_name,
                        method.docs.returns.notes
                    )
                )
            else:
                comment.add_lines("@return " + self.format_type_reference(method.returns))

        return comment
