# Torch
Python package for generating type information from compiled Java code. It is intended to be used to generate type
definitions or bindings for other languages without source code access, as is commonly needed in game modding.
[Rosetta Docs](https://github.com/Rosetta-Docs) files can be used to provide documentation to be used in the output,
such as method descriptions and parameter names (when these are not available in the class files).

## Usage
Torch was developed alongside an application to generate Lua type definitions for *Project Zomboid*'s modding API.
I have done my best to keep the *Zomboid*-specific code separate, but I cannot guarantee that Torch is as suited for
other uses.
The best usage example is that application's [source code](https://github.com/PZ-Umbrella/torch-zomboid).

## Dependencies
Torch uses [a fork of kirjava](https://github.com/demiurgeQuantified/kirjava/tree/type-annotations) to analyse Java files,
and [pyyaml-core](https://github.com/perlpunk/pyyaml-core) to read/write YAML 1.2 
(this is intended to be an optional dependency, but isn't yet).
