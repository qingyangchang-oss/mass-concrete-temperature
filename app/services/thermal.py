"""Thermal calculation engine for mass concrete temperature prediction."""
import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass


@dataclass
class MaterialProperties:
    """Thermal properties of concrete."""
    density: float  # kg/m³
    specific_heat: float  # J/(kg·K)
    thermal_conductivity: float  # W/(m·K)
    thermal_diffusivity: float  # m²/s


@dataclass
class HydrationParameters:
    """Parameters for hydration heat generation."""
    ultimate_temp_rise: float  # °C
    alpha: float  # Rate parameter
    beta: float  # Shape parameter


class ThermalModel:
    """1D Finite difference thermal model for mass concrete."""

    # Heat of hydration (kJ/kg) for different materials
    HEAT_OF_HYDRATION = {
        "OPC": 500,
        "PPC": 420,
        "PSC": 400,
        "GGBS": 450,
        "FlyAsh": 200,
        "SilicaFume": 600,
    }

    # Hydration rate parameters (alpha, beta) by cement type
    HYDRATION_PARAMS = {
        "OPC": (0.05, 0.8),
        "PPC": (0.04, 0.75),
        "PSC": (0.035, 0.7),
    }

    # Thermal properties by aggregate type
    AGGREGATE_PROPERTIES = {
        "limestone": {"conductivity": 2.6, "specific_heat": 880},
        "granite": {"conductivity": 2.8, "specific_heat": 900},
        "basalt": {"conductivity": 2.0, "specific_heat": 850},
    }

    # Convection coefficients (W/m²·K)
    CONVECTION_COEFFS = {
        "steel": 10.0,
        "plywood": 5.0,
        "insulated": 2.0,
        "exposed": 15.0,
    }

    # Curing method effects on surface heat transfer
    CURING_FACTORS = {
        "water": 0.8,  # Reduced convection due to water film
        "compound": 0.9,
        "blankets": 0.4,  # Insulating effect
        "none": 1.0,
    }

    def __init__(
        self,
        cement_type: str,
        cement_content: float,
        ggbs_percent: float = 0,
        fly_ash_percent: float = 0,
        silica_fume_percent: float = 0,
        aggregate_type: str = "limestone",
        calibration: Optional[Dict] = None,
    ):
        self.cement_type = cement_type
        self.cement_content = cement_content
        self.ggbs_percent = ggbs_percent
        self.fly_ash_percent = fly_ash_percent
        self.silica_fume_percent = silica_fume_percent
        self.aggregate_type = aggregate_type

        # Calibration factors (default to 1.0)
        self.calibration = calibration or {
            "heat_coefficient": 1.0,
            "diffusivity_factor": 1.0,
            "convection_factor": 1.0,
        }

        self._calculate_properties()

    def _calculate_properties(self):
        """Calculate effective thermal properties."""
        # Effective heat of hydration (weighted by SCM percentages)
        opc_fraction = 1 - (self.ggbs_percent + self.fly_ash_percent + self.silica_fume_percent) / 100

        heat_total = (
            opc_fraction * self.HEAT_OF_HYDRATION[self.cement_type]
            + (self.ggbs_percent / 100) * self.HEAT_OF_HYDRATION["GGBS"]
            + (self.fly_ash_percent / 100) * self.HEAT_OF_HYDRATION["FlyAsh"]
            + (self.silica_fume_percent / 100) * self.HEAT_OF_HYDRATION["SilicaFume"]
        )

        # Apply calibration
        heat_total *= self.calibration["heat_coefficient"]

        # Ultimate adiabatic temperature rise
        # T_ult = (cement_content * heat_of_hydration) / (density * specific_heat)
        agg_props = self.AGGREGATE_PROPERTIES[self.aggregate_type]
        density = 2400  # kg/m³ typical for concrete
        specific_heat = agg_props["specific_heat"]

        self.ultimate_temp_rise = (self.cement_content * heat_total * 1000) / (density * specific_heat)

        # Hydration parameters
        alpha, beta = self.HYDRATION_PARAMS[self.cement_type]

        # Adjust for SCMs (they slow down hydration)
        scm_factor = 1 - 0.3 * (self.ggbs_percent + self.fly_ash_percent) / 100
        alpha *= scm_factor

        self.hydration_params = HydrationParameters(
            ultimate_temp_rise=self.ultimate_temp_rise,
            alpha=alpha,
            beta=beta,
        )

        # Material properties
        conductivity = agg_props["conductivity"]
        diffusivity = conductivity / (density * specific_heat)
        diffusivity *= self.calibration["diffusivity_factor"]

        self.material = MaterialProperties(
            density=density,
            specific_heat=specific_heat,
            thermal_conductivity=conductivity,
            thermal_diffusivity=diffusivity,
        )

    def adiabatic_temp_rise(self, time_hours: float) -> float:
        """Calculate adiabatic temperature rise at given time."""
        t = time_hours
        params = self.hydration_params
        return params.ultimate_temp_rise * (1 - np.exp(-params.alpha * (t ** params.beta)))

    def heat_generation_rate(self, time_hours: float) -> float:
        """Calculate rate of heat generation (°C/hour)."""
        t = max(time_hours, 0.1)  # Avoid division by zero
        params = self.hydration_params

        # Derivative of adiabatic temperature rise
        rate = (
            params.ultimate_temp_rise
            * params.alpha
            * params.beta
            * (t ** (params.beta - 1))
            * np.exp(-params.alpha * (t ** params.beta))
        )
        return rate

    def simulate(
        self,
        height: float,
        fresh_temp: float,
        ambient_temps: List[float],
        time_step_hours: float = 1.0,
        formwork_type: str = "plywood",
        curing_method: str = "water",
        formwork_removal_hours: float = 72,
        width: float = None,
    ) -> Tuple[List[float], List[float], List[float], List[float]]:
        """
        Run 1D finite difference simulation.

        Returns:
            Tuple of (times, mid_central, mid_side, top_surface) temperatures
        """
        # Spatial discretization
        n_nodes = 21  # Number of nodes through depth
        dz = height / (n_nodes - 1)

        # Time parameters
        dt = time_step_hours * 3600  # Convert to seconds
        n_steps = len(ambient_temps)

        # Stability check (CFL condition)
        alpha = self.material.thermal_diffusivity
        cfl = alpha * dt / (dz ** 2)
        if cfl > 0.5:
            # Reduce time step for stability
            dt = 0.4 * (dz ** 2) / alpha
            substeps = int(np.ceil(time_step_hours * 3600 / dt))
        else:
            substeps = 1

        # Initialize temperature array
        T = np.ones(n_nodes) * fresh_temp

        # Results storage
        times = []
        mid_central = []  # Node at center (deepest point)
        mid_side = []  # Node closer to edge (simulated as different convection)
        top_surface = []  # Top node

        # Convection coefficients
        h_formwork = self.CONVECTION_COEFFS[formwork_type] * self.calibration["convection_factor"]
        h_exposed = self.CONVECTION_COEFFS["exposed"] * self.calibration["convection_factor"]
        curing_factor = self.CURING_FACTORS[curing_method]

        # Width factor for side temperature estimation
        # Narrower sections lose more heat from sides
        width_factor = 1.0
        if width and width < height:
            width_factor = 0.7 + 0.3 * (width / height)

        for step in range(n_steps):
            time_hours = step * time_step_hours
            T_amb = ambient_temps[step]

            # Check if formwork is removed
            formwork_removed = time_hours >= formwork_removal_hours

            # Current convection coefficient at bottom
            if formwork_removed:
                h_bottom = h_exposed * curing_factor
            else:
                h_bottom = h_formwork

            # Top surface always has some exposure
            h_top = h_exposed * curing_factor

            for _ in range(substeps):
                T_new = T.copy()

                # Heat generation for this time step
                Q_gen = self.heat_generation_rate(time_hours + _ * dt / 3600)

                # Internal nodes (finite difference)
                for i in range(1, n_nodes - 1):
                    d2T_dz2 = (T[i + 1] - 2 * T[i] + T[i - 1]) / (dz ** 2)
                    T_new[i] = T[i] + dt * (alpha * d2T_dz2 + Q_gen / 3600)

                # Bottom boundary (conduction to ground, typically constant temp)
                ground_temp = 15  # Assumed ground temperature
                k = self.material.thermal_conductivity
                T_new[0] = T[0] + dt * (
                    alpha * 2 * (T[1] - T[0] - (h_bottom * dz / k) * (T[0] - ground_temp)) / (dz ** 2)
                    + Q_gen / 3600
                )

                # Top boundary (convection with ambient)
                T_new[-1] = T[-1] + dt * (
                    alpha * 2 * (T[-2] - T[-1] - (h_top * dz / k) * (T[-1] - T_amb)) / (dz ** 2)
                    + Q_gen / 3600
                )

                T = T_new

            # Store results
            times.append(time_hours)

            # Mid-depth central (approximately at center)
            center_idx = n_nodes // 2
            mid_central.append(float(T[center_idx]))

            # Mid-depth side (estimate based on additional lateral heat loss)
            # This is a simplified approximation
            side_temp = T[center_idx] - (T[center_idx] - T_amb) * (1 - width_factor) * 0.3
            mid_side.append(float(side_temp))

            # Top surface
            top_surface.append(float(T[-1]))

        return times, mid_central, mid_side, top_surface

    def calculate_differentials(
        self,
        mid_central: List[float],
        top_surface: List[float],
        ambient_temps: List[float],
    ) -> Tuple[List[float], List[float], float]:
        """
        Calculate temperature differentials.

        Returns:
            Tuple of (core_surface_diff, surface_ambient_diff, max_differential)
        """
        core_surface_diff = [c - s for c, s in zip(mid_central, top_surface)]
        surface_ambient_diff = [s - a for s, a in zip(top_surface, ambient_temps)]
        max_diff = max(core_surface_diff)

        return core_surface_diff, surface_ambient_diff, max_diff

    def assess_crack_risk(self, max_differential: float) -> str:
        """Assess cracking risk based on maximum temperature differential."""
        if max_differential < 15:
            return "Low"
        elif max_differential < 20:
            return "Moderate"
        elif max_differential < 25:
            return "High"
        else:
            return "Very High"
