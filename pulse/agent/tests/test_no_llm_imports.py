"""Layer 1 -- static import guard.

The claim under test: nothing on the signal path can reach a model, even by
accident, even three imports down. Detection, metric compilation and ingest
produce every number they report without a model in the loop.

A direct ``import app.llm.client`` in ``detect/severity.py`` is easy to spot in
review. An import three levels down -- ``detect/x.py -> utils/format.py ->
app/llm/client.py`` -- is not, and is exactly how this boundary erodes. So this
walks the AST of every module in the repo, builds the whole first-party import
graph, and checks reachability from each guarded package.

The reverse direction is deliberately allowed and separately asserted: the LLM
side may import from the signal side, because prose is rendered *from* figures
that were already computed. The arrow runs one way.
"""

from __future__ import annotations

import ast
from collections import deque
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

#: Packages that must be reachable-from-nothing-LLM. These are the four the
#: signal path is made of. ``app.attribute`` is listed because the architecture
#: claim names it; it does not exist as a package in this tree (attribution is
#: implemented inside ``app/detect/signals.py``), and the guard reports that
#: rather than silently guarding three packages while claiming four.
GUARDED_PACKAGES = ("app.metrics", "app.detect", "app.attribute", "app.ingest")

#: First-party modules the guarded packages must not reach, at any depth.
FORBIDDEN_FIRST_PARTY = ("app.llm", "app.agent")

#: Third-party model SDKs and the HTTP transports that could carry a model call.
#: ``google.genai`` is the SDK this repo actually uses; the others are listed so
#: the guard keeps holding if the provider is ever swapped.
FORBIDDEN_THIRD_PARTY = (
    "google.genai",
    "google.generativeai",
    "anthropic",
    "openai",
    "httpx",
    "requests",
    "aiohttp",
    "urllib.request",
)

FORBIDDEN = FORBIDDEN_FIRST_PARTY + FORBIDDEN_THIRD_PARTY


def _module_name(path: Path) -> str:
    """``app/detect/signals.py`` -> ``app.detect.signals``; package __init__ maps
    to the package itself."""
    relative = path.relative_to(APP_ROOT.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports_of(path: Path, module: str) -> set[str]:
    """Every module name this file imports, relative imports resolved absolute.

    Deferred imports count. ``app/llm/client.py`` imports the Gemini SDK inside
    the function body precisely so a checkout without it can still boot, and a
    guard that only looked at top-level imports would miss the same trick used
    to sneak a model call onto the signal path.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = module.rsplit(".", 1)[0] if "." in module else module
    found: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # `from . import x` / `from ..pkg import x`
                base_parts = package.split(".")
                trimmed = base_parts[: len(base_parts) - (node.level - 1)] or base_parts[:1]
                base = ".".join(trimmed)
                root = f"{base}.{node.module}" if node.module else base
            else:
                root = node.module or ""
            if not root:
                continue
            found.add(root)
            # `from app.llm import client` imports app.llm.client, not just app.llm.
            found.update(f"{root}.{alias.name}" for alias in node.names if alias.name != "*")
    return found


def _build_graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for path in sorted(APP_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        module = _module_name(path)
        graph[module] = _imports_of(path, module)
    return graph


def _is_forbidden(name: str) -> str | None:
    """The forbidden prefix ``name`` falls under, if any."""
    for prefix in FORBIDDEN:
        if name == prefix or name.startswith(prefix + "."):
            return prefix
    return None


def _resolve(name: str, graph: dict[str, set[str]]) -> str | None:
    """Map an imported name onto a node in the graph.

    ``from app.detect import signals`` yields both ``app.detect`` and
    ``app.detect.signals``; only names that are actually first-party modules
    become edges to follow. Everything else is a leaf -- checked against the
    forbidden list, never traversed.
    """
    if name in graph:
        return name
    return None


def _find_violation(entry: str, graph: dict[str, set[str]]) -> list[str] | None:
    """Breadth-first search for the shortest path from ``entry`` to anything
    forbidden. Returns the chain so the failure names the actual route, not just
    that one exists."""
    queue: deque[list[str]] = deque([[entry]])
    seen = {entry}

    while queue:
        chain = queue.popleft()
        for imported in sorted(graph.get(chain[-1], ())):
            if _is_forbidden(imported):
                return chain + [imported]
            target = _resolve(imported, graph)
            if target is None or target in seen:
                continue
            seen.add(target)
            queue.append(chain + [target])
    return None


def _modules_in(package: str, graph: dict[str, set[str]]) -> list[str]:
    return sorted(m for m in graph if m == package or m.startswith(package + "."))


def _render(chain: list[str]) -> str:
    """``app.detect.severity -> app.utils.format -> app.llm.client``, in the file
    terms the reader will go looking for."""
    return " -> ".join(part.replace("app.", "", 1).replace(".", "/") + ".py" for part in chain)


@pytest.fixture(scope="module")
def graph() -> dict[str, set[str]]:
    return _build_graph()


@pytest.mark.parametrize("package", GUARDED_PACKAGES)
def test_guarded_package_exists(package: str, graph: dict[str, set[str]]) -> None:
    """A guard over a package that isn't there proves nothing.

    This fails for ``app.attribute``: the architecture claim names attribution as
    its own layer, but it is implemented inside ``app/detect/signals.py``
    (``_attribution``). The guard covers that code as part of ``app.detect`` --
    the boundary is intact -- but the package count in the claim is wrong.
    """
    assert _modules_in(package, graph), (
        f"guarded package {package!r} does not exist in {APP_ROOT}; "
        "the import guard cannot cover code that is not there"
    )


@pytest.mark.parametrize("package", GUARDED_PACKAGES)
def test_no_transitive_llm_import(package: str, graph: dict[str, set[str]]) -> None:
    """No module in a guarded package reaches a model, at any depth."""
    modules = _modules_in(package, graph)
    if not modules:
        pytest.skip(f"{package} does not exist; covered by test_guarded_package_exists")

    violations = []
    for module in modules:
        chain = _find_violation(module, graph)
        if chain is not None:
            violations.append(_render(chain))

    assert not violations, "signal path reaches the model layer:\n  " + "\n  ".join(violations)


def test_llm_side_may_import_signal_side(graph: dict[str, set[str]]) -> None:
    """The arrow runs one way, and it is a real arrow.

    Without this, a codebase where the two halves simply never touch would pass
    the guard above for the wrong reason. Prose is rendered *from* computed
    figures, so at least one LLM-facing module must depend on the signal side.
    """
    llm_side = [
        m for m in graph
        if m.startswith(("app.agent", "app.llm", "app.api", "app.actions"))
    ]
    importers = [
        m for m in llm_side
        if any(i.startswith(("app.detect", "app.metrics", "app.ingest")) for i in graph[m])
    ]
    assert importers, (
        "no LLM-facing module imports from the signal side; the one-way dependency "
        "is unproven -- the halves may simply be disconnected"
    )


def test_llm_call_sites_are_enumerable(graph: dict[str, set[str]]) -> None:
    """Every module that can reach ``app.llm`` is one of the three the claim
    allows: narrative prose, action draft text, chat routing.

    This is the positive half of the claim. The guard above says the signal path
    cannot call a model; this says the set that *can* is small, named, and does
    not grow without someone updating this list.
    """
    allowed = {
        "app.api.leadership",    # POST /internal/leadership-narrative -- prose
        "app.api.actions",       # POST /internal/draft-action -- HTTP surface only
        "app.actions.drafters",  # action draft text
        "app.main",              # wires the routers together
        "app.api",               # package __init__ re-exports
    }
    callers = {
        module for module in graph
        if not module.startswith(("app.llm", "app.agent"))
        and _find_violation(module, graph) is not None
    }
    unexpected = sorted(callers - allowed)
    assert not unexpected, (
        "modules can reach the model layer that the architecture claim does not "
        f"account for: {unexpected}"
    )
