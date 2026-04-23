import sys
import os

# Ensure ml_model is implicitly available in python path
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

from ml_model.inference.predict import predict

def prepare_features(data: dict):
    """
    Transforme les données capteurs du robot en format compatible ML.
    """
    return data

def get_crop_recommendation(sensor_data):
    """
    Obtient les recommandations de culture à partir du modèle ML.
    """
    return predict(sensor_data)