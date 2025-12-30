import math

from display.waypoint import Waypoint

def to_rad(deg):
    """Converts degrees to radians."""
    return deg * math.pi / 180

def to_deg(rad):
    """Converts radians to degrees."""
    return rad * 180 / math.pi

def get_bearing(p1:dict, p2:dict)-> float:
    """Calculates the initial bearing from p1 to p2 in degrees."""
    lat1 = to_rad(p1['lat'])
    lat2 = to_rad(p2['lat'])
    d_lon = to_rad(p2['lng'] - p1['lng'])
    
    y = math.sin(d_lon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - \
        math.sin(lat1) * math.cos(lat2) * math.cos(d_lon)
    brng = math.atan2(y, x)
    return (to_deg(brng) + 360) % 360

def get_destination_point(p:dict, distance, bearing):
    """Calculates destination point given start point, distance (m), and bearing (deg)."""
    R = 6371000 # Earth radius in meters
    lat1 = to_rad(p['lat'])
    lon1 = to_rad(p['lng'])
    brng = to_rad(bearing)
    
    lat2 = math.asin(math.sin(lat1) * math.cos(distance / R) +
                     math.cos(lat1) * math.sin(distance / R) * math.cos(brng))
    lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(distance / R) * math.cos(lat1),
                             math.cos(distance / R) - math.sin(lat1) * math.sin(lat2))
    
    # Normalize longitude to -180..+180
    lon2 = (lon2 + 3 * math.pi) % (2 * math.pi) - math.pi

    return {
        'lat': to_deg(lat2),
        'lng': to_deg(lon2)
    }

def get_angle_diff(a, b):
    """Calculates the smallest difference between two angles."""
    diff = a - b
    while diff > 180:
        diff -= 360
    while diff < -180:
        diff += 360
    return diff

def get_quadratic_bezier_points(start:Waypoint, end:Waypoint, control:tuple[float,float], num_points=20):
    """Generates points along a quadratic Bezier curve."""
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        # B(t) = (1-t)^2 * P0 + 2(1-t)t * P1 + t^2 * P2
        lat = (1 - t)**2 * start.latitude + 2 * (1 - t) * t * control[0] + t**2 * end.latitude
        lng = (1 - t)**2 * start.longitude + 2 * (1 - t) * t * control[1] + t**2 * end.longitude
        points.append({'lat': lat, 'lng': lng})
    return points

def get_distance(p1:dict, p2:dict)-> float:
    """Calculates distance between two points in meters using Haversine formula."""
    R = 6371000
    phi1 = to_rad(p1['lat'])
    phi2 = to_rad(p2['lat'])
    dphi = to_rad(p2['lat'] - p1['lat'])
    dlam = to_rad(p2['lng'] - p1['lng'])
    
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def generate_corridor_polygon(route_points:list[Waypoint], round_edges:bool=True)-> tuple[list[dict], list[dict]]:
    """
    Generates the polygon points for the corridor based on route points.
    
    Args:
        route_points: List of dicts with keys 'lat', 'lng', 'width', 
                      and optionally 'segmentType', 'controlLat', 'controlLng'.
        round_edges: Whether to round the outer edge of corners. Defaults to True.
                      
    Returns:
        Tuple containing:
        - List of dicts {'lat': float, 'lng': float} representing the polygon vertices.
        - List of dicts representing path points with added 'left_miter' and 'right_miter' keys.
    """
    if len(route_points) <= 1:
        return [], []

    path_points = []
    
    # Generate dense path points including curves
    for i, p in enumerate(route_points):
        if i == 0:
            path_points.append({'lat': p.latitude, 'lng': p.longitude, 'width': p.width*1852, 'is_waypoint': True})  # Convert nm to m
            continue

        prev = route_points[i - 1]
        if p.end_curved and p.control_latitude is not None and p.control_longitude is not None:
            control = (p.control_latitude, p.control_longitude)
            curve = get_quadratic_bezier_points(prev, p, control)
            
            for idx, cp in enumerate(curve):
                # Avoid duplicate start point
                if idx == 0 and len(path_points) > 0:
                    last = path_points[-1]
                    if abs(last["lat"] - cp["lat"]) < 1e-6 and abs(last["lng"] - cp["lng"]) < 1e-6:
                        continue
                
                t = idx / (len(curve) - 1 or 1)
                w = (prev.width + (p.width - prev.width) * t)*1852  # Interpolate width and convert nm to m
                path_points.append({'lat': cp["lat"], 'lng': cp["lng"], 'width': w, 'is_waypoint': idx == len(curve) - 1})
        else:
            if len(path_points) > 0:
                last = path_points[-1]
                if abs(last["lat"] - p.latitude) < 1e-6 and abs(last["lng"] - p.longitude) < 1e-6:
                    continue
            path_points.append({'lat': p.latitude, 'lng': p.longitude, 'width': p.width*1852, 'is_waypoint': True})

    if len(path_points) < 2:
        return [], []

    left_points = []
    right_points = []
    last_left = None
    last_right = None

    exclusion_zones = []

    for i, p in enumerate(path_points):
        b1 = 0
        b2 = 0
        diff = 0
        
        if i == 0:
            b1 = get_bearing(p, path_points[i + 1])
            b2 = b1
            diff = 0
        elif i == len(path_points) - 1:
            b1 = get_bearing(path_points[i - 1], p)
            b2 = b1
            diff = 0
        else:
            b1 = get_bearing(path_points[i - 1], p)
            b2 = get_bearing(p, path_points[i + 1])
            diff = get_angle_diff(b2, b1)

        miter_factor = 1 / math.cos(to_rad(diff / 2))
        miter_factor = min(miter_factor, 5)
        half_width = p["width"] / 2
        miter_length = half_width * miter_factor
        exclusion_zones.append({'center': p, 'radius': miter_length, 'index': i, 'sharpness': abs(diff)})

        center_bearing = b1 + diff / 2

        # Calculate and save miter points
        if p.get('is_waypoint'):
            # Left Miter
            if diff > 1: # Left is Outside
                dist = half_width if round_edges else miter_length
                p['left_miter'] = get_destination_point(p, dist, center_bearing - 90)
            else: # Left is Inside
                p['left_miter'] = get_destination_point(p, miter_length, center_bearing - 90)

            # Right Miter
            if diff < -1: # Right is Outside
                dist = half_width if round_edges else miter_length
                p['right_miter'] = get_destination_point(p, dist, center_bearing + 90)
            else: # Right is Inside
                p['right_miter'] = get_destination_point(p, miter_length, center_bearing + 90)

        # Left Side
        if diff > 1: # Right Turn -> Left Outside (Round)
            if round_edges:
                steps = math.ceil(diff / 10)
                for s in range(int(steps) + 1):
                    a = b1 - 90 + (diff * s / steps)
                    l = get_destination_point(p, half_width, a)
                    l['source_index'] = i
                    if not last_left or get_distance(last_left, l) > 0.5:
                        left_points.append(l)
                        last_left = l
            else:
                l = get_destination_point(p, half_width * miter_factor, center_bearing - 90)   
                l['source_index'] = i
                left_points.append(l) 
                last_left = l
        else: # Left Inside or Straight
            l = get_destination_point(p, half_width * miter_factor, center_bearing - 90)
            l['source_index'] = i
            left_points.append(l)
            last_left = l

        # Right Side
        if diff < -1: # Left Turn -> Right Outside (Round)
            if round_edges:
                steps = math.ceil(abs(diff) / 10)
                for s in range(int(steps) + 1):
                    a = b1 + 90 + (diff * s / steps)
                    r = get_destination_point(p, half_width, a)
                    r['source_index'] = i
                    if not last_right or get_distance(last_right, r) > 0.5:
                        right_points.append(r)
                        last_right = r
            else:
                r = get_destination_point(p, half_width * miter_factor, center_bearing + 90)
                r['source_index'] = i
                right_points.append(r)
                last_right = r
        else: # Right Inside or Straight
            r = get_destination_point(p, half_width * miter_factor, center_bearing + 90)
            r['source_index'] = i
            right_points.append(r)
            last_right = r

    def filter_points(points):
        filtered = []
        for pt in points:
            keep = True
            for zone in exclusion_zones:
                if zone['index'] == pt['source_index']:
                    continue
                if get_distance(pt, zone['center']) < zone['radius'] - 0.1:
                    pt_sharpness = exclusion_zones[pt['source_index']]['sharpness']
                    zone_sharpness = zone['sharpness']
                    if pt_sharpness >= zone_sharpness:
                        continue
                    keep = False
                    break
            if keep:
                filtered.append(pt)
        return filtered

    final_left = filter_points(left_points)
    final_right = filter_points(right_points)

    # Combine left and right points (right points reversed)
    return final_left + final_right[::-1], path_points