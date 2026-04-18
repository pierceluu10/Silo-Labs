from __future__ import annotations

WOKWI_TOML_TEMPLATE = """[wokwi]
version = 1
firmware = "{firmware}"
elf = "{elf}"
"""


def render_wokwi_toml(firmware_path: str, elf_path: str) -> str:
    return WOKWI_TOML_TEMPLATE.format(firmware=firmware_path, elf=elf_path)
