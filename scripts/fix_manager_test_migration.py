from pathlib import Path

path = Path(__file__).with_name("migrate_manager_dashboard_tests.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
    "from textwrap import dedent\n",
    "from textwrap import dedent, indent\n",
    1,
)

old_start_logic = '''    start = def_index
    cursor = def_index - 1
    while cursor > class_index and lines[cursor].strip():
        start = cursor
        cursor -= 1
'''
new_start_logic = '''    start = def_index
    cursor = def_index - 1

    # Only include decorators that belong to this method.  The old
    # implementation walked across any non-blank line and could consume
    # continuation lines from a multi-line class declaration.
    while cursor > class_index:
        stripped = lines[cursor].lstrip()
        indentation = len(lines[cursor]) - len(stripped)

        if indentation == 4 and stripped.startswith("@"):
            start = cursor
            cursor -= 1
            continue

        # Include continuation lines that belong to a decorator block,
        # but stop before ordinary class-header continuation lines.
        if start < def_index and indentation > 4 and lines[cursor].strip():
            start = cursor
            cursor -= 1
            continue

        break
'''
if old_start_logic not in text:
    raise RuntimeError("start-selection logic not found")
text = text.replace(old_start_logic, new_start_logic, 1)

old_source_logic = '    new_source = dedent(replacement).strip("\\n") + "\\n\\n"\n'
new_source_logic = (
    '    new_source = indent(\n'
    '        dedent(replacement).strip("\\n"),\n'
    '        "    ",\n'
    '    ) + "\\n\\n"\n'
)
if old_source_logic not in text:
    raise RuntimeError("replacement indentation logic not found")
text = text.replace(old_source_logic, new_source_logic, 1)

path.write_text(text, encoding="utf-8")
