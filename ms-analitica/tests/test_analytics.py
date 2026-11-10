import pytest
from app import create_app
from app.database import Base, engine

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            Base.metadata.create_all(bind=engine)
        yield client

def test_health_check(client):
    """Verifica que el servicio esté arriba."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'UP'

def test_pipeline_execution(client):
    """Prueba el ciclo de minería: K-Means, Random Forest y Reglas de Stock."""
    response = client.post('/api/analytics/train')
    assert response.status_code == 201
    
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'metrics' in data
    assert 'kmeans' in data['metrics']
    assert 'random_forest' in data['metrics']
    # Comprobar cumplimiento de RNFM_03
    assert data['metrics']['random_forest']['r2_score'] >= 0.70

def test_get_segmentation_endpoint(client):
    """Verifica lectura de clusters."""
    response = client.get('/api/analytics/segmentation')
    assert response.status_code == 200
    assert isinstance(response.get_json(), list)

def test_get_predictions_endpoint(client):
    """Verifica consulta de predicciones de demanda."""
    response = client.get('/api/analytics/predictions')
    assert response.status_code == 200
    assert isinstance(response.get_json(), list)