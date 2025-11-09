from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from albion.torch import VisibilityLevel


def combine_strings_spaced(*args: str) -> str:
    return " ".join(string for string in args if string != "")


class LuaComment:
    def __init__(self) -> None:
        self.comment: str = ""

    def add_lines(self, text: str) -> None:
        if text == "":
            return

        if self.comment != "":
            self.comment += "\n"

        self.comment += text

    def is_empty(self) -> bool:
        return self.comment == ""

    def __add__(self, other: "LuaComment") -> "LuaComment":
        result = LuaComment()
        result.add_lines(self.comment)
        result.add_lines(other.comment)
        return result

    def __str__(self) -> str:
        if self.comment == "":
            return ""

        return "---" + self.comment.replace("\n", "\n---")

    def __repr__(self) -> str:
        return str(self)
