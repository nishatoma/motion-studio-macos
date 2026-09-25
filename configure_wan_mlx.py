"""Limit the isolated MLX-Video environment's eager imports to the Wan backend.

Upstream's package initializers import LTX audio modules, which require mlx-vlm
even when only `mlx_video.models.wan_2.generate` is used. The setup deliberately
installs just the dependencies used by Wan, so make those initializers lazy.
"""
from __future__ import annotations

import sysconfig
from pathlib import Path

PACKAGE = Path(sysconfig.get_path("purelib")) / "mlx_video"
WAN_IMPORT = "from mlx_video.models.wan_2 import WanModel, WanModelConfig"
WAN_CONTENTS = ('"""Wan-only exports for Motion Studio\'s isolated MLX-Video install."""\n'
                + WAN_IMPORT + '\n__all__ = ["WanModel", "WanModelConfig"]\n')
LTX_CONTENTS = '"""Package namespace needed for Wan\'s BaseModelConfig import."""\n'
TARGETS = (
    (PACKAGE / "__init__.py", WAN_CONTENTS, WAN_IMPORT),
    (PACKAGE / "models" / "__init__.py", WAN_CONTENTS, WAN_IMPORT),
    (PACKAGE / "models" / "ltx_2" / "__init__.py", LTX_CONTENTS,
     "from mlx_video.models.ltx_2.config import"),
)


def main() -> None:
    for target, replacement, required in TARGETS:
        original = target.read_text(encoding="utf-8")
        if original == replacement:
            continue
        if required not in original or "from mlx_video.models.ltx_2" not in original:
            raise RuntimeError(f"Unexpected MLX-Video package initializer: {target}")
        target.write_text(replacement, encoding="utf-8")
        print(f"Disabled unrelated LTX eager imports in {target}")


if __name__ == "__main__":
    main()
