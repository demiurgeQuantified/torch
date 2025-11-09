from albion.torch.types import TypeReference, TypeArgument, WildcardKind, TypeParameter, TypeElement

PRIMITIVE_TYPE_MAP: dict[str, str] = {
    "Z": "boolean",
    "B": "byte",
    "C": "char",
    "S": "short",
    "I": "int",
    "J": "long",
    "F": "float",
    "D": "double",
    "V": "void"
}


def find_balanced(string: str, open: str, close: str, start: int = 0, end: int = -1) -> int:
    depth = 0

    for i, char in enumerate(string[start:end]):
        if char == close:
            if depth == 0:
                return start + i
            depth -= 1
        elif char == open:
            depth += 1

    return -1


ILLEGAL_IDENTIFIER_CHARACTERS: set[str] = {".", ";", "[", "/", "<", ">", ":"}
"""Characters that must not appear in a signature identifier."""


class SignatureParser:
    """

    https://docs.oracle.com/javase/specs/jvms/se21/html/jvms-4.html#jvms-4.7.9.1
    """
    def __init__(self, signature: str) -> None:
        self.signature: str = signature
        self.pos: int = 0

    def peek(self) -> str:
        return self.signature[self.pos]

    def next(self) -> str:
        char = self.signature[self.pos]
        self.pos += 1
        return char

    def parse_identifier(self, peek: bool = False) -> str:
        start = self.pos
        end = self.pos
        while self.signature[end] not in ILLEGAL_IDENTIFIER_CHARACTERS:
            end += 1

        if not peek:
            self.pos = end

        return self.signature[start:end]

    def parse_type_variable(self) -> TypeReference:
        assert self.peek() == "T"
        self.pos += 1

        variable = TypeReference(
            "",
            elements=[
                TypeElement(
                    self.parse_identifier()
                )
            ],
            is_type_variable=True
        )

        if self.next() != ";":
            raise ValueError("Invalid identifier")

        return variable

    def parse_java_type(self) -> TypeReference:
        prefix = self.peek()
        if prefix in PRIMITIVE_TYPE_MAP:
            self.pos += 1
            return TypeReference(
                "",
                elements=[
                    TypeElement(
                        PRIMITIVE_TYPE_MAP[prefix]
                    )
                ]
            )
        return self.parse_reference_type()

    def parse_array_type(self) -> TypeReference:
        assert self.peek() == "["

        self.pos += 1
        type = self.parse_java_type()
        type.array_dimensions += 1

        return type

    def parse_type_arguments(self) -> list[TypeArgument]:
        assert self.peek() == "<"

        type_arguments: list[TypeArgument] = []
        self.pos += 1
        while self.peek() != ">":
            if self.peek() == "*":
                self.pos += 1
                type_arguments.append(
                    TypeArgument(
                        wildcard_kind=WildcardKind.UNBOUNDED
                    )
                )
                continue

            if self.peek() == "+":
                kind = WildcardKind.UPPER_BOUNDED
                self.pos += 1
            elif self.peek() == "-":
                kind = WildcardKind.LOWER_BOUNDED
                self.pos += 1
            else:
                kind = WildcardKind.NONE

            type_arguments.append(
                TypeArgument(
                    type=self.parse_reference_type(),
                    wildcard_kind=kind
                )
            )

        self.pos += 1  # '>'

        return type_arguments

    def parse_simple_class_type(self, identifier: str) -> TypeElement:
        if self.peek() == "<":
            type_arguments = self.parse_type_arguments()
        else:
            type_arguments = []

        return TypeElement(
            identifier.replace("$", "."),
            type_arguments
        )

    def parse_class_type(self) -> TypeReference:
        if not self.next() == "L":
            raise ValueError("Invalid class type")

        package_elements: list[str] = []

        identifier = self.parse_identifier()
        while self.peek() == "/":
            self.next()
            package_elements.append(identifier)
            identifier = self.parse_identifier()

        type_elements: list[TypeElement] = [
            self.parse_simple_class_type(identifier)
        ]

        while self.peek() == ".":
            self.next()
            type_elements.append(
                self.parse_simple_class_type(self.parse_identifier())
            )

        _type = TypeReference(
            "/".join(package_elements),
            type_elements
        )

        if not self.next() == ";":
            raise ValueError("Invalid class type")
        return _type

    def parse_reference_type(self) -> TypeReference:
        match self.signature[self.pos]:
            case "L":
                return self.parse_class_type()
            case "T":
                return self.parse_type_variable()
            case "[":
                return self.parse_array_type()
            case _:
                raise ValueError("Invalid reference type")

    def parse_type_parameters(self) -> list[TypeParameter]:
        assert self.peek() == "<"
        self.pos += 1

        parameters: list[TypeParameter] = []

        while self.peek() != ">":
            name = self.parse_identifier()
            assert self.peek() == ":"
            self.pos += 1

            bounds: list[TypeReference] = []
            if self.peek() != ":":  # class bound
                bounds.append(self.parse_reference_type())

            while self.peek() == ":":  # interface bounds
                self.pos += 1
                bounds.append(self.parse_reference_type())

            parameters.append(
                TypeParameter(
                    name,
                    bounds
                )
            )

        self.pos += 1  # '>'
        return parameters

    def parse_method(self) -> tuple[list[TypeReference], TypeReference, list[TypeParameter]]:
        if self.signature[0] == "<":
            type_parameters = self.parse_type_parameters()
        else:
            type_parameters = []

        assert self.signature[self.pos] == "(", "Method signature must begin with ("
        self.pos += 1  # '('

        parameters: list[TypeReference] = []
        close_bracket = self.signature.find(")")
        while self.pos < close_bracket:
            parameters.append(self.parse_java_type())
        self.pos += 1  # ')'

        returns = self.parse_java_type()

        while self.pos < len(self.signature) and self.peek() == "^":
            # throws... we just ignore these
            self.pos += 1
            match self.peek():
                case "L":
                    self.parse_class_type()
                case "T":
                    self.parse_type_variable()
                case _:
                    raise ValueError("Invalid throws in method signature")

        assert self.pos == len(self.signature), "Method signature parsing did not reach end of string"
        return parameters, returns, type_parameters

    def parse_class(self) -> tuple[TypeReference, list[TypeReference], list[TypeParameter]]:
        if self.signature[0] == "<":
            type_parameters = self.parse_type_parameters()
        else:
            type_parameters = []

        superclass = self.parse_class_type()

        interfaces: list[TypeReference] = []
        while self.pos < len(self.signature):
            interfaces.append(self.parse_class_type())

        assert self.pos == len(self.signature), "Class signature parsing did not reach end of string"

        return superclass, interfaces, type_parameters


def parse_method_signature(signature: str) -> tuple[list[TypeReference], TypeReference, list[TypeParameter]]:
    return SignatureParser(signature).parse_method()


def parse_class_signature(signature: str) -> tuple[TypeReference, list[TypeReference], list[TypeParameter]]:
    return SignatureParser(signature).parse_class()


def parse_type_signature(signature: str) -> TypeReference:
    return SignatureParser(signature).parse_reference_type()
