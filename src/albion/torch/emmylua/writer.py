import string

from collections.abc import Iterable

from albion.torch.types import TypeReference, TypeParameter, TypeArgument, WildcardKind, Executable, Method, \
    Annotatable, Documentable, Parameter
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

DIGITS: set[str] = set(string.digits)

# in lua this is technically locale dependent but who cares
# kahlua probably only likes ascii anyway
VALID_CHARACTERS: set[str] = set(string.ascii_letters)
VALID_CHARACTERS.update(DIGITS)
VALID_CHARACTERS.add("_")


def sanitise_identifier(identifier: str) -> str:
    identifier = "".join(char if char in VALID_CHARACTERS else "_" for char in identifier)

    if identifier[0] in DIGITS or identifier in RESERVED_IDENTIFIERS:
        identifier = "_" + identifier

    return identifier


def is_valid_identifier(identifier: str) -> bool:
    if identifier[0] in DIGITS or identifier in RESERVED_IDENTIFIERS:
        return False

    for char in identifier:
        if char not in VALID_CHARACTERS:
            return False

    return True


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

    def write_function(
            self, name: str, parameters: Iterable[Parameter], has_self: bool = False, containing_table: str = ""
    ) -> str:
        parameter_names = self.get_parameter_names(parameters)

        if is_valid_identifier(name):
            string = "function " + containing_table
            if containing_table != "":
                if has_self:
                    string += ":"
                else:
                    string += "."
            elif has_self:
                # add explicit self parameter since we can't use : without a table
                parameter_names.insert(0, "self")
            string += name
        else:
            string = containing_table + '["' + name + '"] = function'
            # add explicit self parameter since we can't use : when assigning backwards
            parameter_names.insert(0, "self")

        string += f"({", ".join(parameter_names)}) end\n"

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

    def get_parameter_names(self, parameters: Iterable[Parameter]) -> list[str]:
        parameter_names: list[str] = []

        for i, parameter in enumerate(parameters):
            if parameter.name != "":
                name = sanitise_identifier(parameter.name)
            else:
                name = "arg" + str(i)

            parameter_names.append(name)

        return parameter_names

    def annotate_parameters(self, parameters: Iterable[Parameter]) -> LuaComment:
        comment = LuaComment()

        parameter_names = self.get_parameter_names(parameters)

        for i, parameter in enumerate(parameters):
            type_ = self.format_type_reference(parameter.type)
            if parameter.nullable:
                type_ += "?"

            comment.add_lines(
                combine_strings_spaced(
                    "@param", parameter_names[i], type_, parameter.notes
                )
            )

        return comment

    def annotate_executable(self, executable: Executable) -> LuaComment:
        comment = LuaComment()

        comment += self.annotate_deprecation(executable)

        if executable.docs is not None:
            comment.add_lines(executable.docs.notes)

        comment += self.annotate_type_parameters(executable.type_parameters)
        comment += self.annotate_parameters(executable.parameters)

        return comment

    def annotate_method(self, method: Method) -> LuaComment:
        comment = self.annotate_executable(method)

        if method.returns.type.basic != "void":
            if method.returns.name != "":
                return_name = method.returns.name
            elif method.returns.notes != "":
                return_name = "#"
            else:
                return_name = ""

            type_ = self.format_type_reference(method.returns.type)
            if method.returns.nullable:
                type_ += "?"

            comment.add_lines(
                combine_strings_spaced(
                    "@return",
                    type_,
                    return_name,
                    method.returns.notes
                )
            )

        return comment
