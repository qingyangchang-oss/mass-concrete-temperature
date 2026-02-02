"""Model calibration service using least-squares fitting."""
import numpy as np
from scipy.optimize import minimize
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .thermal import ThermalModel


@dataclass
class CalibrationResult:
    """Results from calibration process."""
    heat_coefficient: float
    diffusivity_factor: float
    convection_factor: float
    rmse_before: float
    rmse_after: float
    improvement_percent: float


class CalibrationService:
    """Service for calibrating thermal model against actual measurements."""

    def __init__(self):
        self.bounds = {
            "heat_coefficient": (0.5, 1.5),
            "diffusivity_factor": (0.5, 2.0),
            "convection_factor": (0.5, 2.0),
        }

    def calculate_rmse(
        self,
        predicted: List[float],
        actual: List[float],
    ) -> float:
        """Calculate Root Mean Square Error between predicted and actual values."""
        if not predicted or not actual:
            return float('inf')

        # Align data points
        n = min(len(predicted), len(actual))
        pred = np.array(predicted[:n])
        act = np.array(actual[:n])

        # Filter out None values
        mask = ~np.isnan(act)
        if not mask.any():
            return float('inf')

        pred = pred[mask]
        act = act[mask]

        return float(np.sqrt(np.mean((pred - act) ** 2)))

    def calibrate(
        self,
        mix_design: Dict,
        pour_params: Dict,
        ambient_temps: List[float],
        actual_times: List[float],
        actual_central: List[Optional[float]],
        actual_side: List[Optional[float]] = None,
        actual_surface: List[Optional[float]] = None,
        initial_calibration: Optional[Dict] = None,
    ) -> CalibrationResult:
        """
        Calibrate model parameters using least-squares optimization.

        Args:
            mix_design: Dictionary with cement_type, cement_content, SCM percentages, aggregate_type
            pour_params: Dictionary with height, fresh_temp, formwork_type, curing_method, etc.
            ambient_temps: List of ambient temperatures for simulation
            actual_times: List of measurement times (hours)
            actual_central: List of actual mid-depth central temperatures
            actual_side: Optional list of actual mid-depth side temperatures
            actual_surface: Optional list of actual top surface temperatures
            initial_calibration: Optional starting point for calibration

        Returns:
            CalibrationResult with optimized coefficients
        """
        # Prepare actual data
        actual_central_arr = np.array([t if t is not None else np.nan for t in actual_central])

        if actual_side:
            actual_side_arr = np.array([t if t is not None else np.nan for t in actual_side])
        else:
            actual_side_arr = None

        if actual_surface:
            actual_surface_arr = np.array([t if t is not None else np.nan for t in actual_surface])
        else:
            actual_surface_arr = None

        # Initial calibration values
        if initial_calibration:
            x0 = [
                initial_calibration.get("heat_coefficient", 1.0),
                initial_calibration.get("diffusivity_factor", 1.0),
                initial_calibration.get("convection_factor", 1.0),
            ]
        else:
            x0 = [1.0, 1.0, 1.0]

        # Calculate initial RMSE
        rmse_before = self._evaluate_model(
            x0, mix_design, pour_params, ambient_temps, actual_times,
            actual_central_arr, actual_side_arr, actual_surface_arr
        )

        # Optimization bounds
        bounds = [
            self.bounds["heat_coefficient"],
            self.bounds["diffusivity_factor"],
            self.bounds["convection_factor"],
        ]

        # Run optimization
        result = minimize(
            self._objective_function,
            x0,
            args=(
                mix_design, pour_params, ambient_temps, actual_times,
                actual_central_arr, actual_side_arr, actual_surface_arr
            ),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 100},
        )

        # Extract optimized values
        heat_coef, diff_factor, conv_factor = result.x
        rmse_after = result.fun

        improvement = (rmse_before - rmse_after) / rmse_before * 100 if rmse_before > 0 else 0

        return CalibrationResult(
            heat_coefficient=float(heat_coef),
            diffusivity_factor=float(diff_factor),
            convection_factor=float(conv_factor),
            rmse_before=float(rmse_before),
            rmse_after=float(rmse_after),
            improvement_percent=float(improvement),
        )

    def _objective_function(
        self,
        params: List[float],
        mix_design: Dict,
        pour_params: Dict,
        ambient_temps: List[float],
        actual_times: List[float],
        actual_central: np.ndarray,
        actual_side: Optional[np.ndarray],
        actual_surface: Optional[np.ndarray],
    ) -> float:
        """Objective function for optimization (combined RMSE)."""
        return self._evaluate_model(
            params, mix_design, pour_params, ambient_temps, actual_times,
            actual_central, actual_side, actual_surface
        )

    def _evaluate_model(
        self,
        params: List[float],
        mix_design: Dict,
        pour_params: Dict,
        ambient_temps: List[float],
        actual_times: List[float],
        actual_central: np.ndarray,
        actual_side: Optional[np.ndarray],
        actual_surface: Optional[np.ndarray],
    ) -> float:
        """Evaluate model with given parameters and return combined RMSE."""
        heat_coef, diff_factor, conv_factor = params

        calibration = {
            "heat_coefficient": heat_coef,
            "diffusivity_factor": diff_factor,
            "convection_factor": conv_factor,
        }

        # Create model with calibration
        model = ThermalModel(
            cement_type=mix_design["cement_type"],
            cement_content=mix_design["cement_content"],
            ggbs_percent=mix_design.get("ggbs_percent", 0),
            fly_ash_percent=mix_design.get("fly_ash_percent", 0),
            silica_fume_percent=mix_design.get("silica_fume_percent", 0),
            aggregate_type=mix_design.get("aggregate_type", "limestone"),
            calibration=calibration,
        )

        # Run simulation
        times, pred_central, pred_side, pred_surface = model.simulate(
            height=pour_params["height"],
            fresh_temp=pour_params["fresh_concrete_temp"],
            ambient_temps=ambient_temps,
            time_step_hours=1.0,
            formwork_type=pour_params.get("formwork_type", "plywood"),
            curing_method=pour_params.get("curing_method", "water"),
            formwork_removal_hours=pour_params.get("formwork_removal_hours", 72),
            width=pour_params.get("width"),
        )

        # Interpolate predictions to actual measurement times
        pred_central_interp = np.interp(actual_times, times, pred_central)
        pred_side_interp = np.interp(actual_times, times, pred_side)
        pred_surface_interp = np.interp(actual_times, times, pred_surface)

        # Calculate RMSE for each measurement type
        rmse_values = []

        # Central temperature (weighted most heavily)
        mask = ~np.isnan(actual_central)
        if mask.any():
            rmse_central = np.sqrt(np.mean((pred_central_interp[mask] - actual_central[mask]) ** 2))
            rmse_values.append(rmse_central * 2)  # Weight of 2

        # Side temperature
        if actual_side is not None:
            mask = ~np.isnan(actual_side)
            if mask.any():
                rmse_side = np.sqrt(np.mean((pred_side_interp[mask] - actual_side[mask]) ** 2))
                rmse_values.append(rmse_side)

        # Surface temperature
        if actual_surface is not None:
            mask = ~np.isnan(actual_surface)
            if mask.any():
                rmse_surf = np.sqrt(np.mean((pred_surface_interp[mask] - actual_surface[mask]) ** 2))
                rmse_values.append(rmse_surf)

        if not rmse_values:
            return float('inf')

        return np.mean(rmse_values)

    def interpolate_measurements(
        self,
        times: List[float],
        values: List[Optional[float]],
        target_times: List[float],
    ) -> List[float]:
        """Interpolate sparse measurements to target time points."""
        # Filter out None values
        valid_times = []
        valid_values = []
        for t, v in zip(times, values):
            if v is not None:
                valid_times.append(t)
                valid_values.append(v)

        if len(valid_times) < 2:
            return [valid_values[0] if valid_values else 25.0] * len(target_times)

        return list(np.interp(target_times, valid_times, valid_values))
