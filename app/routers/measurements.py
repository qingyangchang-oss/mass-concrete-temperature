"""Actual measurement endpoints and calibration."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import numpy as np

from ..models.database import get_db, Pour, Prediction, Measurement, Calibration
from ..models.schemas import (
    MeasurementCreate, MeasurementBulkCreate, MeasurementResponse,
    ComparisonResponse, ComparisonPoint, CalibrationResponse,
)
from ..services.calibration import CalibrationService
from ..services.weather import WeatherService

router = APIRouter(prefix="/api", tags=["measurements"])

calibration_service = CalibrationService()
weather_service = WeatherService()


@router.post(
    "/pours/{pour_id}/measurements",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_measurement(
    pour_id: int,
    measurement: MeasurementCreate,
    db: Session = Depends(get_db),
):
    """Add a single measurement for a pour."""
    pour = db.query(Pour).filter(Pour.id == pour_id).first()
    if not pour:
        raise HTTPException(status_code=404, detail="Pour not found")

    db_measurement = Measurement(pour_id=pour_id, **measurement.model_dump())
    db.add(db_measurement)
    db.commit()
    db.refresh(db_measurement)
    return db_measurement


@router.post(
    "/pours/{pour_id}/measurements/bulk",
    response_model=List[MeasurementResponse],
    status_code=status.HTTP_201_CREATED,
)
def add_measurements_bulk(
    pour_id: int,
    data: MeasurementBulkCreate,
    db: Session = Depends(get_db),
):
    """Add multiple measurements for a pour."""
    pour = db.query(Pour).filter(Pour.id == pour_id).first()
    if not pour:
        raise HTTPException(status_code=404, detail="Pour not found")

    measurements = []
    for m in data.measurements:
        db_measurement = Measurement(pour_id=pour_id, **m.model_dump())
        db.add(db_measurement)
        measurements.append(db_measurement)

    db.commit()

    for m in measurements:
        db.refresh(m)

    return measurements


@router.get("/pours/{pour_id}/measurements", response_model=List[MeasurementResponse])
def get_measurements(pour_id: int, db: Session = Depends(get_db)):
    """Get all measurements for a pour."""
    pour = db.query(Pour).filter(Pour.id == pour_id).first()
    if not pour:
        raise HTTPException(status_code=404, detail="Pour not found")

    return db.query(Measurement).filter(
        Measurement.pour_id == pour_id
    ).order_by(Measurement.time_hours).all()


@router.delete("/measurements/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_measurement(measurement_id: int, db: Session = Depends(get_db)):
    """Delete a measurement."""
    measurement = db.query(Measurement).filter(Measurement.id == measurement_id).first()
    if not measurement:
        raise HTTPException(status_code=404, detail="Measurement not found")
    db.delete(measurement)
    db.commit()


@router.get("/pours/{pour_id}/comparison", response_model=ComparisonResponse)
def get_comparison(pour_id: int, db: Session = Depends(get_db)):
    """Compare predicted vs actual temperatures."""
    pour = db.query(Pour).filter(Pour.id == pour_id).first()
    if not pour:
        raise HTTPException(status_code=404, detail="Pour not found")

    predictions = db.query(Prediction).filter(
        Prediction.pour_id == pour_id
    ).order_by(Prediction.time_hours).all()

    measurements = db.query(Measurement).filter(
        Measurement.pour_id == pour_id
    ).order_by(Measurement.time_hours).all()

    # Build comparison data
    data = []
    pred_times = {p.time_hours: p for p in predictions}
    meas_times = {m.time_hours: m for m in measurements}

    all_times = sorted(set(pred_times.keys()) | set(meas_times.keys()))

    for t in all_times:
        pred = pred_times.get(t)
        meas = meas_times.get(t)

        point = ComparisonPoint(
            time_hours=t,
            predicted_central=pred.mid_depth_central if pred else None,
            predicted_side=pred.mid_depth_side if pred else None,
            predicted_surface=pred.top_surface_central if pred else None,
            actual_central=meas.mid_depth_central if meas else None,
            actual_side=meas.mid_depth_side if meas else None,
            actual_surface=meas.top_surface_central if meas else None,
            ambient_temp=pred.ambient_temp if pred else (meas.ambient_temp if meas else None),
        )
        data.append(point)

    # Calculate max differentials
    max_diff_pred = 0
    max_diff_actual = None

    for p in predictions:
        diff = abs(p.mid_depth_central - p.top_surface_central)
        max_diff_pred = max(max_diff_pred, diff)

    if measurements:
        max_diff_actual = 0
        for m in measurements:
            if m.mid_depth_central is not None and m.top_surface_central is not None:
                diff = abs(m.mid_depth_central - m.top_surface_central)
                max_diff_actual = max(max_diff_actual, diff)

    # Calculate RMSE for each point type
    rmse_central = None
    rmse_side = None
    rmse_surface = None

    if measurements and predictions:
        # Interpolate predictions to measurement times
        pred_central = [p.mid_depth_central for p in predictions]
        pred_side = [p.mid_depth_side for p in predictions]
        pred_surface = [p.top_surface_central for p in predictions]
        pred_time_list = [p.time_hours for p in predictions]

        meas_central = []
        meas_side = []
        meas_surface = []
        meas_time_list = []

        for m in measurements:
            meas_time_list.append(m.time_hours)
            meas_central.append(m.mid_depth_central)
            meas_side.append(m.mid_depth_side)
            meas_surface.append(m.top_surface_central)

        # Calculate RMSE
        if any(v is not None for v in meas_central):
            interp_central = np.interp(meas_time_list, pred_time_list, pred_central)
            valid = [(p, a) for p, a in zip(interp_central, meas_central) if a is not None]
            if valid:
                rmse_central = float(np.sqrt(np.mean([(p - a) ** 2 for p, a in valid])))

        if any(v is not None for v in meas_side):
            interp_side = np.interp(meas_time_list, pred_time_list, pred_side)
            valid = [(p, a) for p, a in zip(interp_side, meas_side) if a is not None]
            if valid:
                rmse_side = float(np.sqrt(np.mean([(p - a) ** 2 for p, a in valid])))

        if any(v is not None for v in meas_surface):
            interp_surface = np.interp(meas_time_list, pred_time_list, pred_surface)
            valid = [(p, a) for p, a in zip(interp_surface, meas_surface) if a is not None]
            if valid:
                rmse_surface = float(np.sqrt(np.mean([(p - a) ** 2 for p, a in valid])))

    return ComparisonResponse(
        pour_id=pour_id,
        data=data,
        max_differential_predicted=max_diff_pred,
        max_differential_actual=max_diff_actual,
        rmse_central=rmse_central,
        rmse_side=rmse_side,
        rmse_surface=rmse_surface,
    )


@router.post("/pours/{pour_id}/calibrate", response_model=CalibrationResponse)
async def calibrate_model(pour_id: int, db: Session = Depends(get_db)):
    """Run model calibration based on actual measurements."""
    pour = db.query(Pour).filter(Pour.id == pour_id).first()
    if not pour:
        raise HTTPException(status_code=404, detail="Pour not found")

    measurements = db.query(Measurement).filter(
        Measurement.pour_id == pour_id
    ).order_by(Measurement.time_hours).all()

    if len(measurements) < 3:
        raise HTTPException(
            status_code=400,
            detail="At least 3 measurements required for calibration"
        )

    mix_design = pour.mix_design
    project = pour.project

    # Prepare mix design dict
    mix_design_dict = {
        "cement_type": mix_design.cement_type,
        "cement_content": mix_design.cement_content,
        "ggbs_percent": mix_design.ggbs_percent,
        "fly_ash_percent": mix_design.fly_ash_percent,
        "silica_fume_percent": mix_design.silica_fume_percent,
        "aggregate_type": mix_design.aggregate_type,
    }

    # Prepare pour params
    pour_params = {
        "height": pour.height,
        "width": pour.width,
        "fresh_concrete_temp": pour.fresh_concrete_temp,
        "formwork_type": pour.formwork_type,
        "curing_method": pour.curing_method,
        "formwork_removal_hours": pour.formwork_removal_hours,
    }

    # Get ambient temperatures
    max_time = max(m.time_hours for m in measurements)
    n_hours = int(max_time) + 1

    if project.latitude and project.longitude:
        try:
            ambient_temps = await weather_service.get_historical_and_forecast(
                latitude=project.latitude,
                longitude=project.longitude,
                start_datetime=pour.casting_datetime,
                hours=n_hours,
            )
        except Exception:
            ambient_temps = weather_service.generate_synthetic_temps(hours=n_hours)
    else:
        ambient_temps = weather_service.generate_synthetic_temps(hours=n_hours)

    # Prepare measurement data
    actual_times = [m.time_hours for m in measurements]
    actual_central = [m.mid_depth_central for m in measurements]
    actual_side = [m.mid_depth_side for m in measurements]
    actual_surface = [m.top_surface_central for m in measurements]

    # Get existing calibration if any
    existing = db.query(Calibration).filter(
        Calibration.project_id == project.id,
        Calibration.cement_type == mix_design.cement_type,
    ).first()

    initial_calibration = None
    if existing:
        initial_calibration = {
            "heat_coefficient": existing.heat_coefficient,
            "diffusivity_factor": existing.diffusivity_factor,
            "convection_factor": existing.convection_factor,
        }

    # Run calibration
    result = calibration_service.calibrate(
        mix_design=mix_design_dict,
        pour_params=pour_params,
        ambient_temps=ambient_temps,
        actual_times=actual_times,
        actual_central=actual_central,
        actual_side=actual_side,
        actual_surface=actual_surface,
        initial_calibration=initial_calibration,
    )

    # Store or update calibration
    if existing:
        existing.heat_coefficient = result.heat_coefficient
        existing.diffusivity_factor = result.diffusivity_factor
        existing.convection_factor = result.convection_factor
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        new_calibration = Calibration(
            project_id=project.id,
            cement_type=mix_design.cement_type,
            heat_coefficient=result.heat_coefficient,
            diffusivity_factor=result.diffusivity_factor,
            convection_factor=result.convection_factor,
        )
        db.add(new_calibration)
        db.commit()
        db.refresh(new_calibration)
        return new_calibration


@router.get("/projects/{project_id}/calibrations", response_model=List[CalibrationResponse])
def get_calibrations(project_id: int, db: Session = Depends(get_db)):
    """Get all calibrations for a project."""
    return db.query(Calibration).filter(
        Calibration.project_id == project_id
    ).all()
