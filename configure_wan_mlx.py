"""Limit the isolated MLX-Video environment's eager imports to the Wan backend.

Upstream's package initializers import LTX audio modules, which require mlx-vlm
even when only `mlx_video.models.wan_2.generate` is used. The setup deliberately
installs just the dependencies used by Wan, so make those initializers lazy.
"""
from __future__ import annotations

import sysconfig
from pathlib import Path

PACKAGE = Path(sysconfig.get_path("purelib")) / "mlx_video"
TARGETS = (PACKAGE / "__init__.py", PACKAGE / "models" / "__init__.py")
WAN_IMPORT = "from mlx_video.models.wan_2 import WanModel, WanModelConfig"
CONTENTS = ('"""Wan-only exports for Motion Studio\'s isolated MLX-Video install."""\n'
            + WAN_IMPORT + '\n__all__ = ["WanModel", "WanModelConfig"]\n')


def main() -> None:
    for target in TARGETS:
        original = target.read_text(encoding="utf-8")
        if original == CONTENTS:
            continue
        if WAN_IMPORT not in original or "from mlx_video.models.ltx_2 import" not in original:
            raise RuntimeError(f"Unexpected MLX-Video package initializer: {target}")
        target.write_text(CONTENTS, encoding="utf-8")
        print(f"Disabled unrelated LTX eager imports in {target}")


if __name__ == "__main__":
    main()
