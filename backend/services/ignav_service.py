"""Ignav public API adapter, retaining provider currency and verified prices."""
import os
import requests
from datetime import date
from utils.budget import valid_amount

IGNAV_BASE_URL = 'https://ignav.com/api'

def get_ignav_api_key():
    return os.getenv('IGNAV_API_KEY','').strip()

def resolve_airport_code(location):
    if len(location)==3 and location.isalpha() and location.isupper():
        return location
    response = requests.get(f'{IGNAV_BASE_URL}/airports', params={'q':location}, headers={'X-Api-Key':get_ignav_api_key()}, timeout=10)
    response.raise_for_status()
    rows = response.json()
    return rows[0]['code'] if rows else None

def search_flights(origin, destination, departure_date='', adults=1, children=0, cabin_class='economy', max_stops=None, max_price=None):
    base = {'source':'Ignav', 'origin':origin, 'destination':destination, 'departure_date':departure_date}
    def fail(reason):
        return {**base, 'success':False, 'status':'UNAVAILABLE', 'source_type':'UNAVAILABLE', 'reason':reason}
    if not get_ignav_api_key():
        return fail('IGNAV_API_KEY is not configured')
    try:
        date.fromisoformat(departure_date)
        codes = [resolve_airport_code(origin),resolve_airport_code(destination)]
        if not all(codes):
            return fail('Airport resolution unavailable; supply explicit IATA airport codes')
        payload = {'origin':codes[0], 'destination':codes[1], 'departure_date':departure_date, 'adults':adults, 'children':children, 'cabin_class':cabin_class, 'market':os.getenv('IGNAV_MARKET','IN')}
        if max_stops is not None:
            payload['max_stops'] = max_stops
        response = requests.post(f'{IGNAV_BASE_URL}/fares/one-way', json=payload, headers={'X-Api-Key':get_ignav_api_key()}, timeout=20)
        if response.status_code != 200:
            return fail(f'Ignav HTTP {response.status_code}')
        options = []
        for row in response.json().get('itineraries',[]):
            price = row.get('price') or {}
            amount = valid_amount(price.get('amount'))
            leg = row.get('outbound') or {}
            options.append({'ignav_id':row.get('ignav_id'), 'airline':leg.get('carrier'), 'segments':leg.get('segments',[]),
                'duration_minutes':leg.get('duration_minutes'), 'currency':price.get('currency'), 'price_status':price.get('status'),
                'price':float(amount) if amount is not None and price.get('status')=='verified' else None,
                'raw_price':price, 'passengers':adults+children})
        if not options:
            return fail('No flights returned for requested leg')
        # Ignav amount is the itinerary quote for requested occupancy: never multiply twice.
        verified = [x for x in options if x['currency']=='INR' and x['price'] is not None and (max_price is None or x['price']<=max_price)]
        selected = min(verified,key=lambda x:x['price']) if verified else options[0]
        return {**base, **selected, 'success':True, 'status':'SUCCESS', 'source_type':'LIVE_PROVIDER', 'itineraries':options}
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return fail('Ignav request or response failed')

def search_round_trip_flights(origin,destination,departure_date='',return_date='',passengers=1,**kwargs):
    outbound = search_flights(origin,destination,departure_date,adults=passengers)
    inbound = search_flights(destination,origin,return_date,adults=passengers)
    return {'outbound':outbound,'inbound':inbound, 'success':outbound['success'] and inbound['success']}

def test_ignav_connection():
    return {'provider':'Ignav', 'status':'CONFIGURED' if get_ignav_api_key() else 'UNAVAILABLE'}
