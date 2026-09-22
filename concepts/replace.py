from pathlib import Path
import re

# Converts Typora-style ==highlight== to GitHub-friendly <mark>highlight</mark>
# in every .md file in the CURRENT directory.
#
# Fenced code blocks (``` / ~~~) are left untouched, so code such as
#     if x == y:
# is not changed.

HIGHLIGHT_RE = re.compile(
    r"(?<!\\)==(?=\S)(.*?\S)(?<!\\)==",
    re.DOTALL,
)

FENCE_START_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def convert_inline_code_safe(text: str) -> tuple[str, int]:
    """Convert highlights while temporarily protecting inline `code` spans."""
    protected = []

    def protect(match):
        token = f"\x00INLINE_CODE_{len(protected)}\x00"
        protected.append(match.group(0))
        return token

    temp = re.sub(r"(`+)(.*?)\1", protect, text, flags=re.DOTALL)
    temp, count = HIGHLIGHT_RE.subn(r"<mark>\1</mark>", temp)

    for i, original in enumerate(protected):
        temp = temp.replace(f"\x00INLINE_CODE_{i}\x00", original)

    return temp, count


def convert_markdown(text: str) -> tuple[str, int]:
    lines = text.splitlines(keepends=True)

    output = []
    normal_chunk = []

    in_fence = False
    fence_char = ""
    fence_len = 0
    total_replacements = 0

    def flush_normal():
        nonlocal total_replacements
        if not normal_chunk:
            return

        converted, count = convert_inline_code_safe("".join(normal_chunk))
        output.append(converted)
        total_replacements += count
        normal_chunk.clear()

    for line in lines:
        if not in_fence:
            match = FENCE_START_RE.match(line)
            if match:
                flush_normal()

                fence = match.group(1)
                fence_char = fence[0]
                fence_len = len(fence)
                in_fence = True
                output.append(line)
            else:
                normal_chunk.append(line)

        else:
            output.append(line)

            close_pattern = (
                rf"^[ \t]*{re.escape(fence_char)}"
                rf"{{{fence_len},}}[ \t]*(?:\r?\n)?$"
            )
            if re.match(close_pattern, line):
                in_fence = False
                fence_char = ""
                fence_len = 0

    flush_normal()
    return "".join(output), total_replacements


def main():
    files = sorted(Path.cwd().glob("*.md"))

    if not files:
        print("No .md files found in the current directory.")
        return

    total = 0

    for path in files:
        original = path.read_text(encoding="utf-8")
        converted, count = convert_markdown(original)

        if count:
            path.write_text(converted, encoding="utf-8")
            print(f"{path.name}: replaced {count} highlight(s)")
            total += count
        else:
            print(f"{path.name}: no changes")

    print(
        f"\nDone. Replaced {total} highlight(s) "
        f"across {len(files)} Markdown file(s)."
    )


if __name__ == "__main__":
    main()
