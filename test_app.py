"""Test understory-code."""

from pathlib import Path

import understory.code
from understory.code import app

understory.code.package_dir = Path("test_packages")
understory.code.project_dir = Path("test_projects")


def test_index():
    """Test the main code index."""
    response = app.get("")
    assert response.status == "200 OK"
    assert len(response.dom.select("li")) == 0
