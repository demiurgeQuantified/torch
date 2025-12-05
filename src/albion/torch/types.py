import enum
import dataclasses

from dataclasses import dataclass
from typing import Any, Collection

from albion.torch.docs import DocClass, DocMethod, DocField, DocConstructor, DocNode, DocExecutable
from albion.torch.util import OrderedEnum


class AccessModifier(OrderedEnum):
    PUBLIC = enum.auto()
    PROTECTED = enum.auto()
    PACKAGE = enum.auto()
    PRIVATE = enum.auto()


class WildcardKind(enum.Enum):
    NONE = enum.auto()
    UPPER_BOUNDED = enum.auto()
    LOWER_BOUNDED = enum.auto()
    UNBOUNDED = enum.auto()


class InheritanceModifier(enum.Enum):
    NONE = enum.auto()
    ABSTRACT = enum.auto()
    FINAL = enum.auto()


@dataclass
class TypeElement:
    name: str
    type_arguments: list["TypeArgument"] = dataclasses.field(default_factory=list)

    def __str__(self) -> str:
        if len(self.type_arguments) > 0:
            return f"{self.name}<{", ".join(str(argument) for argument in self.type_arguments)}>"
        return f"{self.name}"

    def __repr__(self) -> str:
        return str(self)


@dataclass
class TypeReference:
    package: str
    elements: list[TypeElement]
    """The class preceded by any enclosing classes."""

    array_dimensions: int = 0
    is_type_variable: bool = False

    @property
    def basic(self) -> str:
        class_name = ".".join(element.name for element in self.elements)
        if self.package != "":
            return self.package + "/" + class_name
        return class_name

    @property
    def type_arguments(self) -> list["TypeArgument"]:
        return self.elements[-1].type_arguments

    def simple_name(self) -> str:
        string = ".".join(str(element) for element in self.elements)
        return string + "[]" * self.array_dimensions

    def __str__(self) -> str:
        string = self.simple_name()

        if self.package != "":
            string = self.package + "/" + string

        return string

    def __repr__(self) -> str:
        return str(self)


PRIMITIVE_TYPE_NAMES = {
    "boolean",
    "byte",
    "char",
    "short",
    "int",
    "long",
    "float",
    "double",
    "void"
}


@dataclass
class TypeArgument:
    type: TypeReference | None = None
    """Represents either the literal type as an argument, or None when WildcardKind is UNBOUNDED"""
    wildcard_kind: WildcardKind = WildcardKind.NONE

    def simple_name(self) -> str:
        match self.wildcard_kind:
            case WildcardKind.LOWER_BOUNDED:
                return f"? super {self.type.simple_name()}"
            case WildcardKind.UPPER_BOUNDED:
                return f"? extends {self.type.simple_name()}"
            case WildcardKind.UNBOUNDED:
                return "?"
            case WildcardKind.NONE:
                return self.type.simple_name()

    def __str__(self) -> str:
        match self.wildcard_kind:
            case WildcardKind.LOWER_BOUNDED:
                return f"? super {str(self.type)}"
            case WildcardKind.UPPER_BOUNDED:
                return f"? extends {str(self.type)}"
            case WildcardKind.UNBOUNDED:
                return "?"
            case WildcardKind.NONE:
                return str(self.type)

    def __repr__(self) -> str:
        return str(self)


@dataclass
class TypeParameter:
    name: str
    bounds: list[TypeReference] = dataclasses.field(default_factory=list)

    def __repr__(self) -> str:
        if len(self.bounds) > 0:
            return f"{self.name} extends {" & ".join(str(bound) for bound in self.bounds)}"
        else:
            return self.name


@dataclass
class Annotation:
    type: TypeReference
    arguments: dict[str, Any]


@dataclass(kw_only=True)
class Named:
    name: str


@dataclass(kw_only=True)
class ClassMember:
    access_modifier: AccessModifier


@dataclass(kw_only=True)
class MayBeStatic:
    static: bool


@dataclass(kw_only=True)
class HasInheritanceModifier:
    inheritance_modifier: InheritanceModifier

    def is_final(self) -> bool:
        return self.inheritance_modifier is InheritanceModifier.FINAL

    def is_abstract(self) -> bool:
        return self.inheritance_modifier is InheritanceModifier.ABSTRACT


@dataclass(kw_only=True)
class HasTypeParameters:
    type_parameters: list[TypeParameter] = dataclasses.field(default_factory=list)


@dataclass(kw_only=True)
class Annotatable:
    annotations: list[Annotation] = dataclasses.field(default_factory=list)

    def get_annotation(self, basic: str) -> Annotation | None:
        for annotation in self.annotations:
            if annotation.type.basic == basic:
                return annotation

        return None


@dataclass(kw_only=True)
class Documentable[T: DocNode]:
    docs: T | None = None


@dataclass(kw_only=True)
class Parameter:
    type: TypeReference
    name: str = ""
    """
    The empty string indicates that no name was found in the class file.
    Obviously the empty string is not actually a valid name.
    """
    notes: str = ""


@dataclass(kw_only=True)
class Executable[T: DocExecutable](Documentable[T], HasTypeParameters, Annotatable):
    parameters: list[Parameter] = dataclasses.field(default_factory=list)

    def __str__(self) -> str:
        string = ""
        if len(self.type_parameters) > 0:
            string = f"<{", ".join(str(parameter) for parameter in self.type_parameters)}>"
        return string + f"({", ".join(str(parameter) for parameter in self.parameters)})"

    def __repr__(self) -> str:
        return str(self)


@dataclass
class Method(ClassMember, Executable[DocMethod], MayBeStatic, Named, HasInheritanceModifier):
    returns: TypeReference

    def __str__(self) -> str:
        string = ""

        if self.access_modifier is not AccessModifier.PACKAGE:
            string += self.access_modifier.name.lower() + " "

        if self.inheritance_modifier is not InheritanceModifier.NONE:
            string += self.inheritance_modifier.name.lower() + " "

        return string + f"{self.name}{Executable.__str__(self)} -> {str(self.returns)}"

    def __repr__(self) -> str:
        return str(self)


class MethodCluster:
    def __init__(self, name: str):
        super().__init__()
        self.name: str = name
        self.methods: list[Method] = []

    def get_with_signature(self, parameter_types: Collection[str], return_type: str) -> Method | None:
        for method in self.methods:
            if method.returns.basic != return_type:
                continue

            if len(parameter_types) != len(method.parameters):
                continue

            for i, _type in enumerate(parameter_types):
                if method.parameters[i].type.basic != _type:
                    continue

            return method

        return None


@dataclass
class Constructor(ClassMember, Executable[DocConstructor]):
    def __str__(self) -> str:
        string = ""

        if self.access_modifier is not AccessModifier.PACKAGE:
            string += self.access_modifier.name.lower() + " "

        return string + Executable.__str__(self)

    def __repr__(self) -> str:
        return str(self)


@dataclass
class Field(ClassMember, MayBeStatic, Named, Annotatable, Documentable[DocField]):
    type: TypeReference


@dataclass
class Class(Named, HasTypeParameters, Annotatable, HasInheritanceModifier, Documentable[DocClass]):
    super: TypeReference | None
    """Superclass. This may only be None for java/lang/Object."""

    access_modifier: AccessModifier

    implements: list[TypeReference] = dataclasses.field(default_factory=list)

    fields: dict[str, Field] = dataclasses.field(default_factory=dict)
    methods: dict[str, MethodCluster] = dataclasses.field(default_factory=dict)
    constructors: list[Constructor] = dataclasses.field(default_factory=list)

    def add_method(self, method: Method) -> None:
        if method.name not in self.methods:
            self.methods[method.name] = MethodCluster(method.name)
        self.methods[method.name].methods.append(method)

    def get_all_methods(self) -> list[Method]:
        methods = []

        for cluster in self.methods.values():
            methods += cluster.methods

        return methods

    def get_all_supertypes(self) -> list[TypeReference]:
        supertypes = []
        if self.super is not None:
            supertypes.append(self.super)
        return supertypes + self.implements

    def package(self) -> str:
        return self.name[:self.name.rfind("/")]

    def simple_name(self) -> str:
        return self.name[self.name.rfind("/") + 1:]

    def __repr__(self) -> str:
        return f"class {self.simple_name()} extends {self.super.simple_name()}"
