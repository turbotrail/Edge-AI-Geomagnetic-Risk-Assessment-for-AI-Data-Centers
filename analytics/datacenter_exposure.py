import yaml
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DataCenterExposure:
    def __init__(self, config_path: str = '../configs/config.yaml'):
        self.config_path = config_path
        self.datacenters = []
        self._load_config()
        
    def _load_config(self):
        """Loads the datacenter configuration from yaml."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    self.datacenters = config.get('datacenters', [])
                logging.info(f"Loaded {len(self.datacenters)} data centers from {self.config_path}")
            except Exception as e:
                logging.error(f"Failed to load datacenter config: {e}")
        else:
            logging.error(f"Config file not found at {self.config_path}")
                
    def calculate_facility_exposure(self, dc_id: str, regional_grid_stress: float) -> float:
        """
        Calculates the specific risk exposure for a single data center.
        
        :param dc_id: The ID of the datacenter.
        :param regional_grid_stress: The estimated grid stress (0.0 - 1.0).
        :return: Exposure risk score (0.0 - 1.0).
        """
        dc = next((item for item in self.datacenters if item["id"] == dc_id), None)
        if not dc:
            logging.warning(f"Data center {dc_id} not found.")
            return 0.0
            
        # Higher redundancy lowers the risk exposure
        redundancy_mitigation = dc.get("redundancy_score", 0.5)
        
        # Base risk is the grid stress, mitigated by facility redundancy
        exposure = regional_grid_stress * (1.0 - redundancy_mitigation)
        
        # Normalize
        return min(max(exposure, 0.0), 1.0)
        
    def get_all_datacenters(self):
        return self.datacenters

if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.yaml')
    exposure_engine = DataCenterExposure(config_path=config_path)
    
    # Simulate a severe regional grid stress event (e.g. 0.8)
    for dc in exposure_engine.get_all_datacenters():
        risk = exposure_engine.calculate_facility_exposure(dc["id"], regional_grid_stress=0.8)
        print(f"{dc['name']} Exposure Risk: {risk:.3f}")
