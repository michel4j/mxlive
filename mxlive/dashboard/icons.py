from typing import Optional, List

from basiclive.core.lims.icons import BaseIconBackend


class BootstrapIconBackend(BaseIconBackend):
    """
    Icon backend for Bootstrap Icons.
    """
    name = "bootstrap-icons"
    base_class = "bi"
    icon_prefix = "bi-"
    stylesheet_urls = ("bootstrap-icons/css/bootstrap-icons.min.css",)
    aliases = {
        "add": "plus-lg",
        "remove": "dash-lg",
        "calendar": "calendar",
        "check": "check-box",
        "edit": "pencil",
        "delete": "trash",
        "move": "arrows-move",
        "view": "eye",
        "list": "list-ul",
        "history": "stopwatch",
        "stats": "activity",
        "usage": "pie-chart",
        "connections": "rss",
        "feedback": "star",
        "support": "headset",
        "areas": "bookmarks",
        "new-area": "bookmark-plus",
        "request": "clipboard-heart",
        "samples": "flask",
        "groups": "collection",
        "profile": "person",
        'journal': 'journals',
        "projects": "briefcase",
        'help': 'question-circle',
        'text-entry': 'body-text',
        'file-entry': 'paperclip',
        'image-entry': 'image',
        'video-entry': 'play-btn',
        'sketch-entry': 'brush',
        'data-entry': 'table',
        "settings": "gear",
        "light-theme": "sun",
        "dark-theme": "moon",
        "auto-theme": "circle-half",
        "home": "house",
        "data": "table",
        "reports": "journal-richtext",
        "send": "send-check",
        "receive": "cart3",
        "shipment": "truck",
        "onsite": "geo-alt",
        "recall": "send-x",
        "error": "exclamation-diamond",
        "comments": "chat-left-text",
        "arrow-left": "arrow-left",
        "arrow-right": "arrow-right",
        "arrow-up": "arrow-up",
        "arrow-down": "arrow-down",
        "requests": "card-checklist",
        "container": "box-seam",
    }

    def get_stylesheet_urls(self) -> List[str]:
        return list(self.stylesheet_urls)

    def resolve_icon_name(self, icon: str) -> str:
        clean = icon.strip()
        if not clean:
            return ""

        canonical = clean.split()[-1]
        target = self.aliases.get(canonical, canonical)
        return f"{self.icon_prefix}{target}"

    def get_css_classes(
        self,
        icon: str,
        size: Optional[str] = None,
        extra_class: str = ""
    ) -> str:
        if not icon or not icon.strip():
            return ""
        parts = [self.base_class, self.resolve_icon_name(icon)]
        size_cls = self.format_size_class(size)
        if size_cls:
            parts.append(size_cls)
        if extra_class and extra_class.strip():
            parts.append(extra_class.strip())
        return " ".join(parts)

    def get_assets(self):
        return {
            "bootstrap-icons": {
                "url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/font/",
                "css": [
                    {
                        "path": "bootstrap-icons.min.css",
                        "sri": "sha256-pdY4ejLKO67E0CM2tbPtq1DJ3VGDVVdqAR6j3ZwdiE4=",
                    },
                    {
                        "path": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/font/fonts/bootstrap-icons.woff",
                        "file": "fonts/bootstrap-icons.woff",
                        "sri": "sha256-9VUTt7WRy4SjuH/w406iTUgx1v7cIuVLkRymS1tUShU=",
                    },
                    {
                        "path": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/font/fonts/bootstrap-icons.woff2",

                        "file": "fonts/bootstrap-icons.woff2",
                        "sri": "sha256-bHVxA2ShylYEJncW9tKJl7JjGf2weM8R4LQqtm/y6mE=",

                    },
                ],
            }
        }

