from dataclasses import dataclass, field

from albion.torch import Type
from albion.torch.docs import DocExecutable, DocMethod, DocConstructor, DocField, DocClass


@dataclass
class RosettaType:
    type: Type
    full: bool
    """
    Whether the type was inferred from a full type.
    If false, the package will not be known, the qualification of the type is impossible to determine.
    The package elements will be within the main class elements: package will be an empty string.
    """
    nullable: bool | None = None

    def __repr__(self) -> str:
        return str(self.type)


@dataclass
class RosettaExecutable[T: DocExecutable]:
    @dataclass
    class Parameter:
        type: RosettaType
        name: str
        notes: str
    docs: T
    parameters: list[Parameter]

    def __repr__(self) -> str:
        return f"({", ".join(parameter.name + ": " + repr(parameter.type) for parameter in self.parameters)})"


@dataclass
class RosettaMethod(RosettaExecutable[DocMethod]):
    returns: RosettaExecutable.Parameter
    static: bool = False

    def __repr__(self) -> str:
        return f"{RosettaExecutable.__repr__(self)} -> {repr(self.returns)}"


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
