This directory is for Nemotron-side project settings and future overrides.

Current layout:
- `mods/nemotron-super/`
  Mounted into the Nemotron container at `/opt/nemotron-super-fix`.

Right now the stack does not require files here to start. The directory exists
so repo-local runtime fixes, patched config files, or helper assets can live
inside the project later without introducing host-specific paths.
