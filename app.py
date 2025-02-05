from flask import Flask, render_template, request, jsonify, send_file
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import sqlite3
import pandas as pd
import time
import json
import os

app = Flask(__name__)

# Initialize geocoder
geolocator = Nominatim(user_agent="geocoder_local")

# Database setup
def init_db():
    conn = sqlite3.connect('geocoder.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cache
                 (address TEXT PRIMARY KEY, lat REAL, lon REAL, timestamp REAL)''')
    conn.commit()
    conn.close()

init_db()

def get_cached_coords(address):
    conn = sqlite3.connect('geocoder.db')
    c = conn.cursor()
    c.execute('SELECT lat, lon FROM cache WHERE address = ?', (address,))
    result = c.fetchone()
    conn.close()
    return result

def cache_coords(address, lat, lon):
    conn = sqlite3.connect('geocoder.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?)',
              (address, lat, lon, time.time()))
    conn.commit()
    conn.close()

def geocode_address(address):
    # Check cache first
    cached = get_cached_coords(address)
    if cached:
        return {'lat': cached[0], 'lon': cached[1]}
    
    # Rate limiting
    time.sleep(1)
    
    try:
        location = geolocator.geocode(address)
        if location:
            cache_coords(address, location.latitude, location.longitude)
            return {'lat': location.latitude, 'lon': location.longitude}
        return {'lat': None, 'lon': None}
    except GeocoderTimedOut:
        return {'lat': None, 'lon': None}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/geocode', methods=['POST'])
def geocode():
    data = request.get_json()
    address = data.get('address')
    name = data.get('name', '')
    
    if not address:
        return jsonify({'error': 'Address is required'}), 400
    
    result = geocode_address(address)
    return jsonify({
        'name': name,
        'address': address,
        'latitude': result['lat'],
        'longitude': result['lon']
    })

@app.route('/geocode_csv', methods=['POST'])
def geocode_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        df = pd.read_csv(file)
        results = []
        for _, row in df.iterrows():
            result = geocode_address(row['address'])
            results.append({
                'name': row.get('name', ''),
                'address': row['address'],
                'latitude': result['lat'],
                'longitude': result['lon']
            })
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/export', methods=['POST'])
def export_results():
    data = request.get_json()
    df = pd.DataFrame(data)
    df.to_csv('results.csv', index=False)
    return send_file('results.csv', as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
