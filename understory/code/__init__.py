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
    args={"project": r"[\w.-]+", "package": r"[\w.-]+"},
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
        web.tx.db.insert("projects", name=name)
        project_dir.mkdir(exist_ok=True)
        warez.Repo(project_dir / name, init=True)
        return web.Created(app.view.project_created(name), f"/{name}")


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
        try:
            project_id = web.tx.db.insert("projects", name=form.name)
        except web.tx.db.IntegrityError:
            project_id = web.tx.db.select(
                "projects", what="rowid, name", where="name = ?", vals=[form.name]
            )[0]["rowid"]
        filename = form.content.fileobj.filename
        web.tx.db.insert(
            "packages",
            project_id=project_id,
            filename=filename,
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
        form.content.save(file_dir=package_dir)
        raise web.Created(
            f"Package `{filename}` has been uploaded.",
            "/{form.name}/packages/{filename}",
        )


@app.control("_pypi/{project}")
class PyPIProject:
    """PyPI project in Simple Repository format."""

    def get(self):
        """Return a simplified list of the project's packages."""
        if packages := web.tx.db.select(
            "packages",
            join="""projects ON packages.project_id = projects.rowid""",
            where="projects.name = ?",
            vals=[self.project],
        ):
            return app.view.pypi_project(self.project, packages)
        raise web.SeeOther(f"https://pypi.org/simple/{self.project}")


@app.control("{project}")
class Project:
    """Project index."""

    def get(self):
        """Return details about the project."""
        return app.view.project(
            self.project,
            warez.Repo(project_dir / self.project),
            web.tx.code.get_packages(self.project),
        )


@app.control("{project}/packages/{package}")
class Package:
    """Project package."""

    def get(self):
        """Return the package file."""
        return package_dir / self.package


@app.model.control
def get_projects(db):
    """Return a list of project names."""
    return [r["name"] for r in db.select("projects", what="name", order="name")]


@app.model.control
def get_packages(db, project):
    """Return a list of packages for given project."""
    return web.tx.db.select(
        "packages",
        join="""projects ON packages.project_id = projects.rowid""",
        where="projects.name = ?",
        vals=[project],
    )
