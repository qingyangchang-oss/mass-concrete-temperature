"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# Project schemas
class ProjectCreate(BaseModel):
    name: str
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    location: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


# Mix Design schemas
class MixDesignCreate(BaseModel):
    name: Optional[str] = None
    cement_type: str = Field(..., pattern="^(OPC|PPC|PSC)$")
    cement_content: float = Field(..., gt=0, le=600)
    ggbs_percent: float = Field(default=0, ge=0, le=80)
    fly_ash_percent: float = Field(default=0, ge=0, le=50)
    silica_fume_percent: float = Field(default=0, ge=0, le=15)
    water_cement_ratio: float = Field(..., gt=0.2, le=0.8)
    aggregate_type: str = Field(..., pattern="^(limestone|granite|basalt)$")


class MixDesignResponse(BaseModel):
    id: int
    project_id: int
    name: Optional[str]
    cement_type: str
    cement_content: float
    ggbs_percent: float
    fly_ash_percent: float
    silica_fume_percent: float
    water_cement_ratio: float
    aggregate_type: str

    class Config:
        from_attributes = True


# Pour schemas
class PourCreate(BaseModel):
    mix_design_id: int
    name: Optional[str] = None
    length: float = Field(..., gt=0)
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0.3)  # Mass concrete typically > 0.3m
    casting_datetime: datetime
    fresh_concrete_temp: float = Field(..., ge=5, le=40)
    formwork_type: str = Field(..., pattern="^(steel|plywood|insulated)$")
    curing_method: str = Field(..., pattern="^(water|compound|blankets|none)$")
    curing_duration_days: int = Field(default=7, ge=0)
    formwork_removal_hours: float = Field(default=72, ge=0)


class PourResponse(BaseModel):
    id: int
    project_id: int
    mix_design_id: int
    name: Optional[str]
    length: float
    width: float
    height: float
    casting_datetime: datetime
    fresh_concrete_temp: float
    formwork_type: str
    curing_method: str
    curing_duration_days: int
    formwork_removal_hours: float
    created_at: datetime

    class Config:
        from_attributes = True


class PourDetailResponse(PourResponse):
    mix_design: MixDesignResponse

    class Config:
        from_attributes = True


# Prediction schemas
class PredictionResponse(BaseModel):
    id: int
    pour_id: int
    time_hours: float
    mid_depth_central: float
    mid_depth_side: float
    top_surface_central: float
    ambient_temp: float
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionRequest(BaseModel):
    duration_hours: int = Field(default=168, ge=24, le=672)  # 1-28 days
    time_step_hours: float = Field(default=1.0, ge=0.5, le=6)


# Measurement schemas
class MeasurementCreate(BaseModel):
    time_hours: float = Field(..., ge=0)
    mid_depth_central: Optional[float] = None
    mid_depth_side: Optional[float] = None
    top_surface_central: Optional[float] = None
    ambient_temp: Optional[float] = None


class MeasurementBulkCreate(BaseModel):
    measurements: List[MeasurementCreate]


class MeasurementResponse(BaseModel):
    id: int
    pour_id: int
    time_hours: float
    mid_depth_central: Optional[float]
    mid_depth_side: Optional[float]
    top_surface_central: Optional[float]
    ambient_temp: Optional[float]
    recorded_at: datetime

    class Config:
        from_attributes = True


# Calibration schemas
class CalibrationResponse(BaseModel):
    id: int
    project_id: Optional[int]
    cement_type: str
    heat_coefficient: float
    diffusivity_factor: float
    convection_factor: float
    updated_at: datetime

    class Config:
        from_attributes = True


# Comparison response
class ComparisonPoint(BaseModel):
    time_hours: float
    predicted_central: Optional[float]
    predicted_side: Optional[float]
    predicted_surface: Optional[float]
    actual_central: Optional[float]
    actual_side: Optional[float]
    actual_surface: Optional[float]
    ambient_temp: Optional[float]


class ComparisonResponse(BaseModel):
    pour_id: int
    data: List[ComparisonPoint]
    max_differential_predicted: float
    max_differential_actual: Optional[float]
    rmse_central: Optional[float]
    rmse_side: Optional[float]
    rmse_surface: Optional[float]


# Weather response
class WeatherForecast(BaseModel):
    datetime: datetime
    temperature: float
    humidity: Optional[float]
    wind_speed: Optional[float]


class WeatherResponse(BaseModel):
    location: str
    latitude: float
    longitude: float
    hourly: List[WeatherForecast]
