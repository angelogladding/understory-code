"""
Host code in the understory.

- Supports [PEP 503 -- Simple Repository API][0] managing Python packages.

[0]: https://www.python.org/dev/peps/pep-0503/

"""

# TODO PEP 592 -- Adding "Yank" Support to the Simple API
# TODO PEP 658 -- Serve Distribution Metadata in the Simple Repository API

from pathlib import Path

import warez
import web

app = web.application(
    __name__,
    db=True,
    prefix="code",
    args={"project": r"[a-z0-9-]+", "package": r"[\w.-]+"},
    model={
        "projects": {
            "name": "TEXT UNIQUE",
        },
        "packages": {
            "project_id": "INTEGER",
            "filename": "TEXT",
            "author": "TEXT",
            "author_email": "TEXT",
            "classifiers": "JSON",
            "home_page": "TEXT",
            "keywords": "JSON",
            "license": "TEXT",
            "project_urls": "JSON",
            "requires_dist": "JSON",
            "requires_python": "TEXT",
            "sha256_digest": "TEXT",
            "summary": "TEXT",
            "version": "TEXT",
        },
    },
)

project_dir = Path("projects")
package_dir = Path("packages")


@app.model.control
def create_project(db, name):
    """Create a project."""
    return db.insert("projects", name=name)


@app.model.control
def get_projects(db):
    """Return a list of project names."""
    return [r["name"] for r in db.select("projects", what="name", order="name")]


@app.model.control
def create_package(db, form):
    """Create a project."""
    try:
        project_id = db.insert("projects", name=form.name)
    except db.IntegrityError:
        project_id = db.select(
            "projects", what="rowid, name", where="name = ?", vals=[form.name]
        )[0]["rowid"]
    return db.insert(
        "packages",
        project_id=project_id,
        filename=form.content.fileobj.filename,
        author=form.author,
        author_email=form.author_email,
        # classifiers=form.classifiers,
        home_page=form.home_page,
        # keywords=form.keywords.split(","),
        license=form.license,
        # project_urls=form.project_urls if "project_urls" in form else [],
        # requires_dist=form.requires_dist,
        requires_python=form.requires_python,
        sha256_digest=form.sha256_digest,
        summary=form.summary,
        version=form.version,
    )


@app.model.control
def get_packages(db, project):
    """Return a list of packages for given project."""
    return db.select(
        "packages",
        join="""projects ON packages.project_id = projects.rowid""",
        where="projects.name = ?",
        vals=[project],
    )


@app.wrap
def connect_model(handler, main_app):
    """Connect the model to the current transaction."""
    web.tx.code = app.model(web.tx.db)
    yield


@app.control("")
class Code:
    """Code index."""

    def get(self):
        """Return a list of projects."""
        return app.view.index(web.tx.code.get_projects())

    def post(self):
        """Create a project."""
        name = web.form("name").name
        web.tx.code.create_project(name)
        project_dir.mkdir(exist_ok=True)
        warez.Repo(project_dir / name, init=True)
        return web.Created(app.view.project_created(name), f"/{name}")


@app.control("{project}")
class Project:
    """Project index."""

    def get(self, project):
        """Return details about the project."""
        return app.view.project(
            project,
            warez.Repo(project_dir / project),
            web.tx.code.get_packages(project),
        )


@app.control("{project}/packages/{package}")
class Package:
    """Project package."""

    def get(self, project, package):
        """Return the package file."""
        return package_dir / package


@app.control("_pypi")
class PyPIIndex:
    """PyPI repository in Simple Repository format."""

    def get(self):
        """Return a simplified list of the repository's projects."""
        return app.view.pypi_index(web.tx.code.get_projects())

    def post(self):
        """Accept PyPI package upload."""
        form = web.form(":action")
        if form[":action"] != "file_upload":
            raise web.BadRequest(f"Provided `:action={form[':action']}` not supported.")
        web.tx.code.create_package(form)
        form.content.save(file_dir=package_dir)
        raise web.Created(
            "Package has been uploaded.",
            "/{form.name}/packages/{form.content.fileobj.filename}",
        )


@app.control("_pypi/{project}")
class PyPIProject:
    """PyPI project in Simple Repository format."""

    def get(self, project):
        """Return a simplified list of the project's packages."""
        if packages := web.tx.code.get_packages(project):
            return app.view.pypi_project(project, packages)
        raise web.SeeOther(f"https://pypi.org/simple/{project}")
