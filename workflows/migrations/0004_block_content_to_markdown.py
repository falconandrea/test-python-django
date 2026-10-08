import re
from html.parser import HTMLParser

from django.db import migrations


class LegacyRichTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.current_tag = None
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag in {"h1", "h2", "h3", "p"}:
            self._finish_block()
            self.current_tag = tag

    def handle_endtag(self, tag):
        if tag == self.current_tag:
            self._finish_block()

    def handle_data(self, data):
        if self.current_tag is None and data.strip():
            self.current_tag = "p"
        if self.current_tag is not None:
            self.current_text.append(data)

    def _finish_block(self):
        content = "".join(self.current_text).strip()
        if content:
            if self.current_tag in {"h1", "h2", "h3"}:
                content = f'{"#" * int(self.current_tag[1])} {content}'
            self.blocks.append(content)
        self.current_tag = None
        self.current_text = []

    def as_markdown(self):
        self._finish_block()
        return "\n\n".join(self.blocks)


def convert_legacy_html_to_markdown(apps, schema_editor):
    Block = apps.get_model("workflows", "Block")
    legacy_tags = re.compile(r"</?(?:h[1-3]|p)(?:\s|>)", re.IGNORECASE)

    for block in Block.objects.filter(kind="rich_text").iterator():
        if not legacy_tags.search(block.content):
            continue
        parser = LegacyRichTextParser()
        parser.feed(block.content)
        Block.objects.filter(pk=block.pk).update(content=parser.as_markdown())


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0003_sharelink_responses_admin_label"),
    ]

    operations = [
        migrations.RunPython(convert_legacy_html_to_markdown, migrations.RunPython.noop),
    ]
