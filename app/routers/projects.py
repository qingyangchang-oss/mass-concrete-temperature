"""Project and pour CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..models.database import get_db, Project, MixDesign, Pour
from ..models.schemas import (
    ProjectCreate, ProjectResponse,
    MixDesignCreate, MixDesignResponse,
    PourCreate, PourResponse, PourDetailResponse,
)

router = APIRouter(prefix="/api", tags=["projects"])


# Project endpoints
@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    """List all projects."""
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project."""
    db_project = Project(**project.model_dump())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Delete a project and all associated data."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()


# Mix Design endpoints
@router.get("/projects/{project_id}/mix-designs", response_model=List[MixDesignResponse])
def list_mix_designs(project_id: int, db: Session = Depends(get_db)):
    """List mix designs for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.mix_designs


@router.post(
    "/projects/{project_id}/mix-designs",
    response_model=MixDesignResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mix_design(
    project_id: int,
    mix_design: MixDesignCreate,
    db: Session = Depends(get_db),
):
    """Create a new mix design for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate SCM percentages don't exceed 100%
    total_scm = mix_design.ggbs_percent + mix_design.fly_ash_percent + mix_design.silica_fume_percent
    if total_scm > 80:
        raise HTTPException(
            status_code=400,
            detail="Total SCM percentage cannot exceed 80%"
        )

    db_mix = MixDesign(project_id=project_id, **mix_design.model_dump())
    db.add(db_mix)
    db.commit()
    db.refresh(db_mix)
    return db_mix


@router.get("/mix-designs/{mix_id}", response_model=MixDesignResponse)
def get_mix_design(mix_id: int, db: Session = Depends(get_db)):
    """Get mix design by ID."""
    mix_design = db.query(MixDesign).filter(MixDesign.id == mix_id).first()
    if not mix_design:
        raise HTTPException(status_code=404, detail="Mix design not found")
    return mix_design


# Pour endpoints
@router.get("/projects/{project_id}/pours", response_model=List[PourResponse])
def list_pours(project_id: int, db: Session = Depends(get_db)):
    """List pours for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.pours


@router.post(
    "/projects/{project_id}/pours",
    response_model=PourResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pour(
    project_id: int,
    pour: PourCreate,
    db: Session = Depends(get_db),
):
    """Create a new pour for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify mix design exists and belongs to project
    mix_design = db.query(MixDesign).filter(MixDesign.id == pour.mix_design_id).first()
    if not mix_design:
        raise HTTPException(status_code=404, detail="Mix design not found")
    if mix_design.project_id != project_id:
        raise HTTPException(status_code=400, detail="Mix design does not belong to this project")

    db_pour = Pour(project_id=project_id, **pour.model_dump())
    db.add(db_pour)
    db.commit()
    db.refresh(db_pour)
    return db_pour


@router.get("/pours/{pour_id}", response_model=PourDetailResponse)
def get_pour(pour_id: int, db: Session = Depends(get_db)):
    """Get pour by ID with mix design details."""
    pour = db.query(Pour).filter(Pour.id == pour_id).first()
    if not pour:
        raise HTTPException(status_code=404, detail="Pour not found")
    return pour


@router.delete("/pours/{pour_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pour(pour_id: int, db: Session = Depends(get_db)):
    """Delete a pour and all associated data."""
    pour = db.query(Pour).filter(Pour.id == pour_id).first()
    if not pour:
        raise HTTPException(status_code=404, detail="Pour not found")
    db.delete(pour)
    db.commit()
