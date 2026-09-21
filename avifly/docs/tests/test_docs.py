import pytest
from django.test import Client
from django.urls import reverse

from avifly.conftest import make_user
from avifly.docs import documents as docs

pytestmark = pytest.mark.django_db


def test_the_repository_docs_are_listed():
    found = docs.documents()
    assert "guide" in found
    assert found["guide"].title == "Avifly Tracker"
    assert "modules" in found  # docs/modules.md


def test_index_lists_them(owner_client):
    response = owner_client.get(reverse("docs:index"))
    assert response.status_code == 200
    assert "Avifly Tracker" in response.content.decode()


def test_page_renders_markdown_as_html(owner_client):
    response = owner_client.get(reverse("docs:page", args=["guide"]))
    body = response.content.decode()
    assert response.status_code == 200
    assert "<table>" in body  # the tables survive
    assert 'id="technology"' in body  # headings get anchors for the contents list
    assert reverse("docs:page", args=["modules"]) in body  # links between docs are rewritten


def test_unknown_document_is_404(owner_client):
    assert owner_client.get(reverse("docs:page", args=["nope"])).status_code == 404


def test_docs_need_a_signed_in_user(client):
    response = client.get(reverse("docs:index"))
    assert response.status_code == 302
    assert reverse("account_login") in response["Location"]


def test_any_signed_in_user_can_read_them(client):
    client.force_login(make_user("helper"))
    assert client.get(reverse("docs:index")).status_code == 200


def test_private_notes_are_owners_only(client, owner_client, tmp_path, settings):
    """Files named with a leading underscore are private: owners see them, others don't."""
    settings.BASE_DIR = tmp_path
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("# Public\n\nFor everyone.\n")
    (tmp_path / "docs" / "_developer.md").write_text("# Private notes\n\nFor owners.\n")

    assert docs.documents()["developer"].owner_only is True
    body = owner_client.get(reverse("docs:index")).content.decode()
    assert "Private notes" in body
    assert owner_client.get(reverse("docs:page", args=["developer"])).status_code == 200

    client.force_login(make_user("helper2"))
    body = client.get(reverse("docs:index")).content.decode()
    assert "Private notes" not in body
    assert client.get(reverse("docs:page", args=["developer"])).status_code == 404


def test_images_are_served_from_the_docs_folder(owner_client, tmp_path, settings):
    """Screenshots in docs/images/ show up in the app; badges from other sites become labels."""
    settings.BASE_DIR = tmp_path
    (tmp_path / "docs" / "images").mkdir(parents=True)
    (tmp_path / "docs" / "images" / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "docs" / "notes.txt").write_text("not an image folder file")
    (tmp_path / "README.md").write_text(
        "# Guide\n\n![Dashboard](docs/images/shot.png)\n\n"
        "![Tests](https://img.shields.io/badge/tests-passing-green)\n"
    )

    body = owner_client.get(reverse("docs:page", args=["guide"])).content.decode()
    image_url = reverse("docs:image", args=["shot.png"])
    assert f'src="{image_url}"' in body
    assert "img.shields.io" not in body  # the page's CSP would block it anyway
    assert ">Tests</span>" in body

    response = owner_client.get(image_url)
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert "default-src 'none'" in response["Content-Security-Policy"]

    images = reverse("docs:index") + "images/"
    assert owner_client.get(images + "missing.png").status_code == 404
    assert owner_client.get(images + "..%2Fnotes.txt").status_code == 404
    assert owner_client.get(images + "..%2F..%2FREADME.md").status_code == 404

    response = Client().get(image_url)  # not signed in
    assert response.status_code == 302
    assert reverse("account_login") in response["Location"]
