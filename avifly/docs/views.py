from __future__ import annotations

from django.http import FileResponse, Http404
from django.views.generic import TemplateView

from avifly.docs import documents as docs


class DocIndexView(TemplateView):
    template_name = "docs/index.html"

    def get_context_data(self, **kwargs):
        available = docs.documents_for(self.request.user)
        return super().get_context_data(documents=available.values(), **kwargs)


class DocPageView(TemplateView):
    template_name = "docs/page.html"

    def get_context_data(self, **kwargs):
        document = docs.get_document(self.kwargs["slug"], self.request.user)
        if document is None:
            raise Http404
        return super().get_context_data(
            page=docs.render(document),
            documents=docs.documents_for(self.request.user).values(),
            **kwargs,
        )


def image(request, name: str):
    """An image from docs/images/, for the documentation pages (signed-in users)."""
    path = docs.image_path(name)
    if path is None:
        raise Http404
    response = FileResponse(path.open("rb"), content_type=docs.IMAGE_TYPES[path.suffix.lower()])
    # An SVG is a document in its own right: make sure nothing inside it can ever run.
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    response["Cache-Control"] = "private, max-age=3600"
    return response
