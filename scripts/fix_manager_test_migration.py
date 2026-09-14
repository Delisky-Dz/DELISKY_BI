from pathlib import Path

path = Path(__file__).with_name("migrate_manager_dashboard_tests.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "from textwrap import dedent\n",
    "from textwrap import dedent, indent\n",
    1,
)
text = text.replace(
    '    new_source = dedent(replacement).strip("\\n") + "\\n\\n"\n',
    '    new_source = indent(\n'
    '        dedent(replacement).strip("\\n"),\n'
    '        "    ",\n'
    '    ) + "\\n\\n"\n',
    1,
)
path.write_text(text, encoding="utf-8")
