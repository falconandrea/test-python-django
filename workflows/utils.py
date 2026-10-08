import nh3
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt


_MARKDOWN = MarkdownIt("commonmark", {"html": False})
_ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}


def render_markdown(value):
    rendered = _MARKDOWN.render(value or "")
    sanitized = nh3.clean(
        rendered,
        tags=_ALLOWED_TAGS,
        attributes={"a": {"href", "title"}},
        url_schemes={"http", "https", "mailto"},
    )
    return mark_safe(sanitized)
