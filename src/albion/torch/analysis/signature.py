from albion.torch.types import ClassType, TypeArgument, WildcardKind, TypeParameter, TypeElement, \
    TypeVariable, Type, Primitive, ReferenceType, Array, \
    PrimitiveTypeName

PRIMITIVE_TYPE_MAP: dict[str, PrimitiveTypeName] = {
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

    https://docs.oracle.com/javase/specs/jvms/se25/html/jvms-4.html
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

    def parse_type_variable(self) -> TypeVariable:
        assert self.peek() == "T"
        self.pos += 1

        variable = TypeVariable(self.parse_identifier())

        if self.next() != ";":
            raise ValueError("Invalid identifier")

        return variable

    def parse_java_type(self) -> Type:
        prefix = self.peek()
        if prefix in PRIMITIVE_TYPE_MAP:
            self.pos += 1
            return Primitive(PRIMITIVE_TYPE_MAP[prefix])
        return self.parse_reference_type()

    def parse_array_type(self) -> Array:
        assert self.peek() == "["

        dimensions = 0
        while self.peek() == "[":
            dimensions += 1
            self.pos += 1

        return Array(self.parse_java_type(), dimensions)

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
            identifier,
            type_arguments
        )

    def parse_class_type(self) -> ClassType:
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
        
        # split elements that contain $s into separate elements
        # this is done for consistency with rosetta,
        # because the rosetta parser won't be able to determine if elements should be merged or not
        # that would be avoidable if rosetta used type names in the internal format, but i don't want to make breaking changes
        # as far as i know there is no benefit to keeping them together anyway
        split_elements: list[TypeElement] = []
        for element in type_elements:
            element_parts = element.name.split("$")
            if len(element_parts) > 1:
                element.name = element_parts[-1]
                for part in element_parts[:-1]:
                    split_elements.append(
                        TypeElement(
                            part,
                            []
                        )
                    )

            split_elements.append(element)
            continue
            

        _type = ClassType(
            "/".join(package_elements),
            split_elements
        )

        if not self.next() == ";":
            raise ValueError("Invalid class type")
        return _type

    def parse_reference_type(self) -> ReferenceType:
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

            bounds: list[ReferenceType] = []
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

    def parse_method(self) -> tuple[list[Type], Type, list[TypeParameter]]:
        if self.signature[0] == "<":
            type_parameters = self.parse_type_parameters()
        else:
            type_parameters = []

        assert self.signature[self.pos] == "(", "Method signature must begin with ("
        self.pos += 1  # '('

        parameters: list[Type] = []
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

    def parse_class(self) -> tuple[ClassType, list[ClassType], list[TypeParameter]]:
        if self.signature[0] == "<":
            type_parameters = self.parse_type_parameters()
        else:
            type_parameters = []

        superclass = self.parse_class_type()

        interfaces: list[ClassType] = []
        while self.pos < len(self.signature):
            interfaces.append(self.parse_class_type())

        assert self.pos == len(self.signature), "Class signature parsing did not reach end of string"

        return superclass, interfaces, type_parameters


def parse_method_signature(signature: str) -> tuple[list[Type], Type, list[TypeParameter]]:
    return SignatureParser(signature).parse_method()


def parse_class_signature(signature: str) -> tuple[ClassType, list[ClassType], list[TypeParameter]]:
    return SignatureParser(signature).parse_class()


def parse_type_signature(signature: str) -> Type:
    return SignatureParser(signature).parse_java_type()
