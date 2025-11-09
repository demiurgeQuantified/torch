from dataclasses import dataclass, field

from albion.torch import TypeReference
from albion.torch.docs import DocExecutable, DocMethod, DocConstructor, DocField, DocClass


@dataclass
class RosettaType:
    type: TypeReference
    full: bool
    """
    Whether the type was inferred from a full type.
    If false, the package will not be known, the qualification of the type is impossible to determine.
    The package elements will be within the main class elements: package will be an empty string.
    """

    def __repr__(self) -> str:
        return str(self.type)


@dataclass
class RosettaExecutable[T: DocExecutable]:
    docs: T
    parameter_types: list[RosettaType]

    def __repr__(self) -> str:
        parameter_strings: list[str] = []
        for i, parameter in enumerate(self.parameter_types):
            parameter_strings.append(f"{self.docs.parameters[i].name}: {repr(parameter)}")

        return f"({", ".join(parameter_strings)})"


@dataclass
class RosettaMethod(RosettaExecutable[DocMethod]):
    return_type: RosettaType
    static: bool = False

    def __repr__(self) -> str:
        return f"{RosettaExecutable.__repr__(self)} -> {repr(self.return_type)}"


RosettaConstructor = RosettaExecutable[DocConstructor]


@dataclass
class RosettaField:
    docs: DocField
    static: bool


@dataclass
class RosettaClass:
    docs: DocClass
    fields: dict[str, RosettaField] = field(default_factory=dict)
    methods: dict[str, list[RosettaMethod]] = field(default_factory=dict)
    constructors: list[RosettaConstructor] = field(default_factory=list)

    def get_methods(self, name: str) -> list[RosettaMethod]:
        if name not in self.methods:
            self.methods[name] = []
        return self.methods[name]


RosettaPackage = dict[str, RosettaClass]

RosettaContext = dict[str, RosettaPackage]
