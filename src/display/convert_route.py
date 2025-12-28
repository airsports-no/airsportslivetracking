import json
import uuid
import argparse
import sys
import os

def convert_legacy_json(route_layers):
    features = []
    
    # Find track layer to process path and waypoints
    track_layer = next((x for x in route_layers if x.get('feature_type') == 'track'), None)
    
    if track_layer:
        # 1. Route Path (LineString)
        if 'geojson' in track_layer:
            path_feature = {
                "type": "Feature",
                "properties": {
                    "featureType": "route_path"
                },
                "geometry": track_layer['geojson']['geometry']
            }
            features.append(path_feature)
            
        # 2. Waypoints (Points)
        track_points = track_layer.get('track_points', [])
        for i, point in enumerate(track_points):
            # Heuristic for width: if small (< 10), assume km/NM and convert to meters (x1000).
            # Otherwise assume meters. old.json uses 1, new format uses ~1000-1852.
            raw_width = float(point.get('gateWidth', 1852))
            width = raw_width * 1852 if raw_width < 10 else raw_width
            try:
                coords = [point['position']['lng'], point['position']['lat']]
            except KeyError:
                coords=track_layer["geojson"]["geometry"]["coordinates"][i]
            wp_feature = {
                "type": "Feature",
                "properties": {
                    "id": str(uuid.uuid4()),
                    "name": point.get('name', f"TP {i}"),
                    "pointType": point.get('gateType', 'tp'), # Maps sp/tp/fp directly
                    "featureType": "route_waypoint",
                    "width": width,
                    "isTiming": point.get('timeCheck', False),
                    "isPassing": True, # Default to True for imported points
                    "sequence": i
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": coords
                }
            }
            features.append(wp_feature)
            
    # Process other layers (Gates, Zones, Observations)
    for layer in route_layers:
        ft = layer.get('feature_type')
        if ft == 'track':
            continue
            
        geo = layer.get('geojson', {}).get('geometry')
        if not geo:
            continue
            
        props = {
            "id": str(uuid.uuid4()),
            "name": layer.get('name', 'Unknown')
        }
        
        feature = {
            "type": "Feature",
            "properties": props,
            "geometry": geo
        }
        
        if ft == 'to':
            props['gateType'] = 'takeoff'
            props['featureType'] = 'takeoff_gate'
            props['width'] = 50
            features.append(feature)
        elif ft == 'ldg':
            props['gateType'] = 'landing'
            props['featureType'] = 'landing_gate'
            props['width'] = 50
            features.append(feature)
        elif ft == 'photo':
            props['featureType'] = 'observation_photo'
            features.append(feature)
        elif ft in ['prohibited', 'penalty', 'info']:
            props['polygonType'] = ft
            props['featureType'] = 'zone'
            features.append(feature)
        elif ft == 'gate':
            props['polygonType'] = 'waypoint'
            props['featureType'] = 'waypoint_polygon'
            features.append(feature)
            
    return {
        "type": "FeatureCollection",
        "features": features
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert legacy route JSON to new GeoJSON format.")
    parser.add_argument("input", help="Input JSON file path")
    parser.add_argument("output", help="Output GeoJSON file path")
    
    args = parser.parse_args()
    
    with open(args.input, 'r', encoding='utf-8') as f:
        old_data = json.load(f)
    
    new_data = convert_legacy_json(old_data)
    
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, indent=2)
        
    print(f"Converted {args.input} -> {args.output}")