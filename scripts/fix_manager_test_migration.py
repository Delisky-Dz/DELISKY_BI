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

    # Look at the contiguous block immediately before the method.  Include
    # that block only when it actually contains a method decorator.  This
    # preserves multi-line class headers while still removing multi-line
    # @patch(...) decorators from the legacy test.
    cursor = def_index - 1
    while cursor > class_index and lines[cursor].strip():
        cursor -= 1
    candidate_start = cursor + 1
    if any(
        lines[index].startswith("    @")
        for index in range(candidate_start, def_index)
    ):
        start = candidate_start
'''
if old_start_logic not in text:
    raise RuntimeError("start-selection logic not found")
text = text.replace(old_start_logic, new_start_logic, 1)

old_end_logic = '''    end = class_end
    for index in range(def_index + 1, class_end):
        line = lines[index]
        if line.startswith("    @") or line.startswith("    def "):
            end = index
            break

    while end > start and not lines[end - 1].strip():
        end -= 1
'''
new_end_logic = '''    end = class_end
    for index in range(def_index + 1, class_end):
        line = lines[index]
        if line.startswith("    @") or line.startswith("    def "):
            end = index
            break
        # A non-indented, non-blank line means the class has ended even when
        # module-level imports/constants appear before the next class.
        if line.strip() and not line[0].isspace():
            end = index
            break

    while end > start and not lines[end - 1].strip():
        end -= 1
'''
if old_end_logic not in text:
    raise RuntimeError("end-selection logic not found")
text = text.replace(old_end_logic, new_end_logic, 1)

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
