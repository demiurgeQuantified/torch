import zipfile

from pathlib import Path
from abc import ABC, abstractmethod


class ClassPathEntry(ABC):
    @abstractmethod
    def get_file(self, path: str) -> Path | None: ...

    @abstractmethod
    def get_all_classes(self) -> list[Path]: ...


class ClassPathDirectory(ClassPathEntry):
    def __init__(self, path: Path) -> None:
        assert path.is_dir()
        self.directory: Path = path

    def get_file(self, path: str) -> Path | None:
        path = self.directory / path
        if path.is_file():
            return path

        return None

    def get_all_classes(self) -> list[Path]:
        return list(self.directory.rglob("*.class"))


class ClassPathJar(ClassPathEntry):
    def __init__(self, path: Path) -> None:
        assert path.is_file()
        self.jar: zipfile.ZipFile = zipfile.ZipFile(path)

    def get_file(self, path: str) -> Path | None:
        path = zipfile.Path(self.jar, path)
        if path.is_file():
            return path

        return None

    def get_all_classes(self) -> list[Path]:
        classes: list[Path] = []

        for name in self.jar.namelist():
            if name.endswith(".class"):
                classes.append(zipfile.Path(self.jar, name))

        return classes


class FileSystem:
    def __init__(self, classpath: list[Path]) -> None:
        self.classpath: list[ClassPathEntry] = []
        for path in classpath:
            if path.is_file():
                self.classpath.append(ClassPathJar(path))
            else:
                self.classpath.append(ClassPathDirectory(path))

    def find_class_file(self, name: str) -> Path | None:
        # it could be faster to bake a map of class names to their locations rather than scan every path every time
        #  if we assume we will always open every class (which is close to true)
        #  it's a reduction from O(n) to O(1)
        name = name.replace(".", "$")

        name = name + ".class"

        for entry in self.classpath:
            path = entry.get_file(name)
            if path is not None:
                return path

        return None

    def get_all_classes(self) -> list[Path]:
        classes: list[Path] = []
        for entry in self.classpath:
            classes += entry.get_all_classes()

        return classes
