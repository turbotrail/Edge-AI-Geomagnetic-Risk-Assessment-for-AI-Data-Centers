import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class GridStressIndex:
    def __init__(self):
        """
        Initializes the Grid Stress Index calculator.
        """
        # Critical E-field threshold (V/km) that typically causes severe GIC
        self.critical_e_field_threshold = 5.0 
        
    def calculate_index(self, e_field_series: np.ndarray, latitude: float) -> float:
        """
        Calculates a normalized Grid Stress Index (0.0 to 1.0) based on the Geoelectric field 
        and geomagnetic latitude.
        
        :param e_field_series: 1D numpy array of estimated E-field in V/km
        :param latitude: The magnetic latitude of the grid region
        :return: Grid Stress Index (float 0.0 to 1.0)
        """
        if len(e_field_series) == 0:
            return 0.0
            
        max_e_field = np.max(np.abs(e_field_series))
        
        # Latitude weighting: higher latitudes (closer to poles) experience much stronger GICs
        # Simplified multiplier: Lat 40 -> 1.0, Lat 60 -> 1.5, Lat >70 -> 2.0
        lat_weight = 1.0
        abs_lat = abs(latitude)
        if abs_lat >= 70:
            lat_weight = 2.0
        elif abs_lat >= 50:
            lat_weight = 1.0 + ((abs_lat - 50) / 20.0)
            
        # Calculate raw stress
        raw_stress = (max_e_field / self.critical_e_field_threshold) * lat_weight
        
        # Normalize to 0.0 - 1.0
        normalized_stress = min(max(raw_stress, 0.0), 1.0)
        
        logging.info(f"Calculated Grid Stress Index: {normalized_stress:.3f} (Max E-field: {max_e_field:.2f} V/km, Lat: {latitude})")
        return normalized_stress
        
    def calculate_index_from_dbdt(self, dbdt_series: np.ndarray, latitude: float, ground_resistivity_ohm_m: float = 1000.0, bt: float = 0.0, bz: float = 0.0) -> float:
        """
        Calculates a normalized Grid Stress Index based on real ground magnetometer dB/dt data and IMF conditions.
        
        :param dbdt_series: 1D numpy array of dB/dt in nT/min
        :param latitude: The magnetic latitude of the grid region
        :param ground_resistivity_ohm_m: Ground resistivity in Ohm-meters
        :param bt: Interplanetary Magnetic Field total strength (nT)
        :param bz: Interplanetary Magnetic Field Z-component (nT)
        """
        if len(dbdt_series) == 0:
            return 0.0
            
        max_dbdt = np.max(np.abs(dbdt_series))
        
        # Simplified 1D Earth Conductivity E-field estimation:
        # E (V/km) is roughly proportional to dB/dt and sqrt(resistivity)
        # Using an empirical scaling factor for mid-latitudes
        scaling_factor = 0.05 * np.sqrt(ground_resistivity_ohm_m / 1000.0)
        max_e_field = max_dbdt * scaling_factor
        
        # IMF Coupling Modifier (Mz)
        # Southward Bz (< 0) effectively couples solar wind to magnetosphere, increasing GIC intensity
        imf_multiplier = 1.0
        if bz < 0:
            imf_multiplier = 1.0 + (bt * abs(bz)) / 100.0
            
        max_e_field *= imf_multiplier
        
        return self.calculate_index(np.array([max_e_field]), latitude)

if __name__ == "__main__":
    stress_engine = GridStressIndex()
    # Dummy E-field array
    e_field = np.array([0.5, 2.1, 4.5, 1.0])
    
    # Test for mid-latitude (Virginia)
    stress_va = stress_engine.calculate_index(e_field, 39.0)
    print(f"Grid Stress (Virginia): {stress_va:.2f}")
    
    # Test for high-latitude (Sweden)
    stress_sweden = stress_engine.calculate_index(e_field, 65.0)
    print(f"Grid Stress (Sweden): {stress_sweden:.2f}")
