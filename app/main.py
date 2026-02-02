"""FastAPI application entry point."""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path

from .models.database import init_db, get_db, Project, Pour, MixDesign
from .routers import projects_router, predictions_router, measurements_router

# Initialize database
init_db()

# Create FastAPI app
app = FastAPI(
    title="Mass Concrete Temperature Modeling Platform",
    description="Predict temperature profiles in mass concrete structures",
    version="1.0.0",
)

# Mount static files
static_path = Path(__file__).parent.parent / "static"
templates_path = Path(__file__).parent.parent / "templates"

app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
templates = Jinja2Templates(directory=str(templates_path))

# Include routers
app.include_router(projects_router)
app.include_router(predictions_router)
app.include_router(measurements_router)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page showing all projects."""
    db = next(get_db())
    projects = db.query(Project).order_by(Project.created_at.desc()).all()

    # Get pour counts for each project
    project_data = []
    for p in projects:
        pour_count = db.query(Pour).filter(Pour.project_id == p.id).count()
        project_data.append({
            "project": p,
            "pour_count": pour_count,
        })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "projects": project_data,
    })


@app.get("/projects/new", response_class=HTMLResponse)
async def new_project_form(request: Request):
    """Form for creating a new project."""
    return templates.TemplateResponse("new_project.html", {
        "request": request,
    })


@app.get("/projects/{project_id}/view", response_class=HTMLResponse)
async def view_project(request: Request, project_id: int):
    """View project details and pours."""
    db = next(get_db())
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "message": "Project not found",
        }, status_code=404)

    mix_designs = db.query(MixDesign).filter(MixDesign.project_id == project_id).all()
    pours = db.query(Pour).filter(Pour.project_id == project_id).order_by(Pour.casting_datetime.desc()).all()

    return templates.TemplateResponse("project_detail.html", {
        "request": request,
        "project": project,
        "mix_designs": mix_designs,
        "pours": pours,
    })


@app.get("/pours/{pour_id}/results", response_class=HTMLResponse)
async def view_results(request: Request, pour_id: int):
    """View prediction results for a pour."""
    db = next(get_db())
    pour = db.query(Pour).filter(Pour.id == pour_id).first()
    if not pour:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "message": "Pour not found",
        }, status_code=404)

    return templates.TemplateResponse("results.html", {
        "request": request,
        "pour": pour,
        "project": pour.project,
        "mix_design": pour.mix_design,
    })


@app.get("/pours/{pour_id}/calibration", response_class=HTMLResponse)
async def calibration_page(request: Request, pour_id: int):
    """Calibration and measurement input page."""
    db = next(get_db())
    pour = db.query(Pour).filter(Pour.id == pour_id).first()
    if not pour:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "message": "Pour not found",
        }, status_code=404)

    return templates.TemplateResponse("calibration.html", {
        "request": request,
        "pour": pour,
        "project": pour.project,
    })
