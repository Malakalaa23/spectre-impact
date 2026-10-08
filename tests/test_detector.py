from backend.detector.resource_detector import ResourceDetector


def test_detects_mapped_and_unknown_files():
    detector = ResourceDetector("backend/data/resource_map.json")
    result = detector.detect_resources([
        "terraform/customer_database.tf",
        "services/login/app.py",
        "frontend/unknown.jsx",
    ])
    assert result.detected_resources == ["customer_database", "login_service"]
    assert result.unknown_resources == ["frontend/unknown.jsx"]


def test_detects_files_anywhere_inside_a_service_folder():
    detector = ResourceDetector("backend/data/resource_map.json")
    result = detector.detect_resources(["services/payment/routes/charge.py"])
    assert result.detected_resources == ["payment_service"]
    assert result.unknown_resources == []
