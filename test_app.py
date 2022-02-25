import pathlib

import understory.code
from understory.code import app

understory.code.package_dir = pathlib.Path("test_packages")
understory.code.project_dir = pathlib.Path("test_projects")


def test_index():
    response = app.get("")
    assert response.status == "200 OK"
    assert len(response.dom.select("li")) == 0
