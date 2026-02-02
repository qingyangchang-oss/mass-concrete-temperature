"""SQLAlchemy database models."""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_URL = "sqlite:///./data/mass_concrete.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Project(Base):
    """Project model for organizing pours."""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    location = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    mix_designs = relationship("MixDesign", back_populates="project", cascade="all, delete-orphan")
    pours = relationship("Pour", back_populates="project", cascade="all, delete-orphan")
    calibrations = relationship("Calibration", back_populates="project", cascade="all, delete-orphan")


class MixDesign(Base):
    """Concrete mix design specifications."""
    __tablename__ = "mix_designs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(255))
    cement_type = Column(String(50))  # OPC, PPC, PSC
    cement_content = Column(Float)  # kg/m³
    ggbs_percent = Column(Float, default=0)
    fly_ash_percent = Column(Float, default=0)
    silica_fume_percent = Column(Float, default=0)
    water_cement_ratio = Column(Float)
    aggregate_type = Column(String(50))  # limestone, granite, basalt

    project = relationship("Project", back_populates="mix_designs")
    pours = relationship("Pour", back_populates="mix_design")


class Pour(Base):
    """Concrete pour/casting event."""
    __tablename__ = "pours"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    mix_design_id = Column(Integer, ForeignKey("mix_designs.id"), nullable=False)
    name = Column(String(255))
    length = Column(Float)  # meters
    width = Column(Float)  # meters
    height = Column(Float)  # meters
    casting_datetime = Column(DateTime)
    fresh_concrete_temp = Column(Float)  # °C
    formwork_type = Column(String(50))  # steel, plywood, insulated
    curing_method = Column(String(50))  # water, compound, blankets, none
    curing_duration_days = Column(Integer)
    formwork_removal_hours = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="pours")
    mix_design = relationship("MixDesign", back_populates="pours")
    predictions = relationship("Prediction", back_populates="pour", cascade="all, delete-orphan")
    measurements = relationship("Measurement", back_populates="pour", cascade="all, delete-orphan")


class Prediction(Base):
    """Temperature predictions at various points."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    pour_id = Column(Integer, ForeignKey("pours.id"), nullable=False)
    time_hours = Column(Float)
    mid_depth_central = Column(Float)  # Core temperature
    mid_depth_side = Column(Float)  # Near formwork
    top_surface_central = Column(Float)  # Exposed surface
    ambient_temp = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    pour = relationship("Pour", back_populates="predictions")


class Measurement(Base):
    """Actual temperature measurements."""
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    pour_id = Column(Integer, ForeignKey("pours.id"), nullable=False)
    time_hours = Column(Float)
    mid_depth_central = Column(Float)
    mid_depth_side = Column(Float)
    top_surface_central = Column(Float)
    ambient_temp = Column(Float)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    pour = relationship("Pour", back_populates="measurements")


class Calibration(Base):
    """Calibration coefficients for model tuning."""
    __tablename__ = "calibration"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    cement_type = Column(String(50))
    heat_coefficient = Column(Float, default=1.0)
    diffusivity_factor = Column(Float, default=1.0)
    convection_factor = Column(Float, default=1.0)
    updated_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="calibrations")


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
