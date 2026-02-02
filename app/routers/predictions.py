"""Temperature prediction endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..models.database import get_db, Pour, Prediction, Calibration
from ..models.schemas import PredictionResponse, PredictionRequest
from ..services.thermal import ThermalModel
from ..services.weather import WeatherService

router = APIRouter(prefix="/api", tags=["predictions"])

weather_service = WeatherService()


@router.post("/pours/{pour_id}/predict", response_model=List[PredictionResponse])
async def run_prediction(
    pour_id: int,
    request: PredictionRequest = None,
    db: Session = Depends(get_db),
):
    """Run temperature prediction for a pour."""
    if request is None:
        request = PredictionRequest()

    pour = db.query(Pour).filter(Pour.id == pour_id).first()
    if not pour:
        raise HTTPException(status_code=404, detail="Pour not found")

    mix_design = pour.mix_design
    project = pour.project

    # Get calibration if available
    calibration = db.query(Calibration).filter(
        Calibration.project_id == project.id,
        Calibration.cement_type == mix_design.cement_type,
    ).first()

    calibration_dict = None
    if calibration:
        calibration_dict = {
            "heat_coefficient": calibration.heat_coefficient,
            "diffusivity_factor": calibration.diffusivity_factor,
            "convection_factor": calibration.convection_factor,
        }

    # Create thermal model
    model = ThermalModel(
        cement_type=mix_design.cement_type,
        cement_content=mix_design.cement_content,
        ggbs_percent=mix_design.ggbs_percent,
        fly_ash_percent=mix_design.fly_ash_percent,
        silica_fume_percent=mix_design.silica_fume_percent,
        aggregate_type=mix_design.aggregate_type,
        calibration=calibration_dict,
    )

    # Get ambient temperatures
    n_hours = int(request.duration_hours / request.time_step_hours) + 1

    if project.latitude and project.longitude:
        try:
            ambient_temps = await weather_service.get_historical_and_forecast(
                latitude=project.latitude,
                longitude=project.longitude,
                start_datetime=pour.casting_datetime,
                hours=n_hours,
            )
        except Exception:
            # Fallback to synthetic temperatures
            ambient_temps = weather_service.generate_synthetic_temps(
                base_temp=25.0,
                daily_range=10.0,
                hours=n_hours,
            )
    else:
        ambient_temps = weather_service.generate_synthetic_temps(
            base_temp=25.0,
            daily_range=10.0,
            hours=n_hours,
        )

    # Run simulation
    times, mid_central, mid_side, top_surface = model.simulate(
        height=pour.height,
        fresh_temp=pour.fresh_concrete_temp,
        ambient_temps=ambient_temps,
        time_step_hours=request.time_step_hours,
        formwork_type=pour.formwork_type,
        curing_method=pour.curing_method,
        formwork_removal_hours=pour.formwork_removal_hours,
        width=pour.width,
    )

    # Clear existing predictions for this pour
    db.query(Prediction).filter(Prediction.pour_id == pour_id).delete()

    # Store predictions
    predictions = []
    for i, t in enumerate(times):
        pred = Prediction(
            pour_id=pour_id,
            time_hours=t,
            mid_depth_central=mid_central[i],
            mid_depth_side=mid_side[i],
            top_surface_central=top_surface[i],
            ambient_temp=ambient_temps[i] if i < len(ambient_temps) else ambient_temps[-1],
        )
        db.add(pred)
        predictions.append(pred)

    db.commit()

    # Refresh to get IDs
    for pred in predictions:
        db.refresh(pred)

    return predictions


@router.get("/pours/{pour_id}/predictions", response_model=List[PredictionResponse])
def get_predictions(pour_id: int, db: Session = Depends(get_db)):
    """Get all predictions for a pour."""
    pour = db.query(Pour).filter(Pour.id == pour_id).first()
    if not pour:
        raise HTTPException(status_code=404, detail="Pour not found")

    return db.query(Prediction).filter(
        Prediction.pour_id == pour_id
    ).order_by(Prediction.time_hours).all()


@router.get("/weather")
async def get_weather(
    latitude: float = Query(...),
    longitude: float = Query(...),
    hours: int = Query(default=168, ge=24, le=384),
):
    """Get weather forecast for a location."""
    try:
        forecasts = await weather_service.get_forecast(latitude, longitude, hours)
        return {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": forecasts,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/geocode")
async def geocode_location(city: str = Query(..., min_length=2)):
    """Convert city name to coordinates."""
    result = await weather_service.geocode_location(city)
    if not result:
        raise HTTPException(status_code=404, detail="Location not found")

    lat, lon, name = result
    return {
        "latitude": lat,
        "longitude": lon,
        "name": name,
    }
