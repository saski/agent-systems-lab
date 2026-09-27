"""One-shot worker: receive an ephemeral credential on stdin, return JSON."""

import json
import os
import sys
from pathlib import Path

from systems_lab.runtime import LangChainRuntime


def main() -> None:
    request = json.load(sys.stdin)
    runtime = LangChainRuntime(Path(os.environ.get("LAB_ROOT", ".")))
    result = runtime.run(request["role"], request["gateway_url"], request["token"])
    print(result.model_dump_json())


if __name__ == "__main__":
    main()
