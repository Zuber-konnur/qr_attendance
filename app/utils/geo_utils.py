import math

EARTH_RADIUS_METERS = 6371000.0

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points in meters
    using the Haversine formula.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_METERS * c

def verify_student_location(student_lat: float, student_lon: float, active_locations: list):
    """
    Check if the student is within the perimeter radius of ANY active location.
    Returns: (is_inside: bool, matched_or_closest_location, distance_in_meters: float)
    """
    if not active_locations:
        return True, None, 0.0

    closest_loc = None
    min_dist = float('inf')

    for loc in active_locations:
        dist = haversine_distance(student_lat, student_lon, loc.latitude, loc.longitude)
        if dist <= loc.radius_meters:
            return True, loc, round(dist, 1)
        if dist < min_dist:
            min_dist = dist
            closest_loc = loc

    return False, closest_loc, round(min_dist, 1)
