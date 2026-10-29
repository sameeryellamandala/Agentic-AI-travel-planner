"""Inter-city estimates only. Never invent distance, train inventory or live fares."""
import json
import os
import re
from urllib.parse import urlparse
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import requests
from utils.budget import valid_amount

CONFIG = Path(__file__).resolve().parents[1] / 'config' / 'transport_rates.json'


def unavailable(reason):
    return {'success': False, 'status': 'UNAVAILABLE', 'source_type': 'UNAVAILABLE', 'distance_km': None, 'fares': [], 'price': None, 'reason': reason}


ALIASES = {'bangalore': ('bangalore', 'bengaluru'), 'bengaluru': ('bangalore', 'bengaluru'), 'vizag': ('vizag', 'visakhapatnam'), 'vijaywada': ('vijaywada', 'vijayawada')}
RAIL_SOURCE_HOSTS = {'indiarailinfo.com', 'ixigo.com', 'railyatri.in', 'erail.in', 'confirmtkt.com', 'indianrail.gov.in'}


def railway_search_results(origin, destination):
    from ddgs import DDGS
    return DDGS(timeout=12).text(f'{origin} to {destination} railway train route distance km', backend='duckduckgo', max_results=8)


def distance_from_search_result(row, origin, destination):
    url = row.get('href', '')
    host = urlparse(url).hostname or ''
    text = ' '.join([row.get('title', ''), row.get('body', '')])
    lower = text.casefold()
    if not any(host == allowed or host.endswith('.'+allowed) for allowed in RAIL_SOURCE_HOSTS):
        return None
    if not all(any(alias in lower for alias in ALIASES.get(city.strip().casefold(), (city.strip().casefold(),))) for city in (origin, destination)):
        return None
    if not re.search(r'\b(?:rail|railway|train|trains)\b', lower) or re.search(r'\b(?:road|driving|straight.line|flight|air)\b', lower):
        return None
    pattern = r'(?:shortest(?:\s+rail)?\s+distance|rail(?:way)?\s+distance|distance(?:\s+of)?)[^0-9]{0,45}(\d[\d,]*(?:\.\d+)?)\s*(?:km|kilometres|kilometers)\b'
    matches = re.findall(pattern, lower)
    amounts = {Decimal(value.replace(',', '')) for value in matches}
    if len(amounts) != 1:
        return None
    amount = amounts.pop()
    if not 0 < amount < 20000:
        return None
    return {'success': True, 'origin': origin, 'destination': destination, 'distance_km': float(amount), 'distance_type': 'rail', 'source': url, 'source_type': 'WEB_SOURCE', 'search_engine': 'DuckDuckGo', 'evidence': text, 'note': 'Reported railway route distance; train and station choices may vary. Verify before booking.'}


def search_railway_distance(origin, destination):
    try:
        rows = railway_search_results(origin, destination)
        for row in rows:
            distance = distance_from_search_result(row, origin, destination)
            if distance:
                return distance
        return unavailable('Distance unavailable: DuckDuckGo returned no unambiguous railway-route distance for both endpoints. Train fare cannot be calculated.')
    except Exception:
        return unavailable('Distance unavailable: DuckDuckGo railway search failed. Train fare cannot be calculated.')


def is_local_mobility(origin, destination):
    first, second = origin.strip().casefold(), destination.strip().casefold()
    if first == second:
        return True
    if re.search(r'\b(?:hotel|beach|temple|restaurant|airport|sightseeing|taxi|auto)\b', first+' '+second):
        return True
    return first.endswith(' '+second) or second.endswith(' '+first)


def calculate_distance(origin, destination, supplied_distance=None):
    if supplied_distance is not None:
        amount = valid_amount(supplied_distance)
        if amount is not None and amount > 0:
            return {'success': True, 'distance_km': float(amount), 'origin': origin, 'destination': destination, 'source': 'User supplied railway route distance', 'source_type': 'USER_PROVIDED', 'distance_type': 'rail'}
    url = os.getenv('RAIL_DISTANCE_URL', '').strip()
    if not url:
        return search_railway_distance(origin, destination)
    try:
        headers = {'Authorization': 'Bearer '+os.environ['RAIL_DISTANCE_API_KEY']} if os.getenv('RAIL_DISTANCE_API_KEY') else {}
        response = requests.get(url, params={'origin': origin, 'destination': destination}, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        amount = valid_amount(data.get('distance_km'))
        matches = str(data.get('origin', '')).strip().casefold() == origin.strip().casefold() and str(data.get('destination', '')).strip().casefold() == destination.strip().casefold()
        if not matches or data.get('distance_type') != 'rail' or amount is None or amount <= 0 or not data.get('source'):
            return unavailable('Distance unavailable: provider did not verify this railway route. Train fare cannot be calculated.')
        return {**data, 'success': True, 'source_type': 'LIVE_PROVIDER', 'distance_km': float(amount)}
    except (requests.RequestException, ValueError, TypeError):
        return unavailable('Distance unavailable: railway distance provider failed. Train fare cannot be calculated.')


def estimate_train_fares(distance_info, passengers=1, selected_class='3A'):
    distance = valid_amount(distance_info.get('distance_km'))
    if not distance_info.get('success') or distance is None or distance <= 0:
        return unavailable(distance_info.get('reason', 'Distance unavailable. Train fare cannot be calculated.'))
    try:
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
        classes = config['train']
        if selected_class not in classes:
            return unavailable('Unsupported railway class')
        def money(value):
            return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        fares = []
        for code, rule in classes.items():
            rate, tax_rate = Decimal(rule['rate_per_km']), Decimal(rule['tax_rate'])
            base = money(distance * rate)
            tax = money(base * tax_rate)
            total = base + tax
            fares.append({'class': code, 'name': rule['name'], 'distance_km': float(distance), 'rate_per_km': float(rate), 'tax_rate': float(tax_rate), 'base_fare': float(base), 'tax': float(tax), 'total_fare': float(total), 'passengers': passengers, 'party_total': float(total * passengers), 'source': 'CONFIGURED_ESTIMATE'})
        selected = next(fare for fare in fares if fare['class'] == selected_class)
        return {'success': True, 'status': 'SUCCESS', 'mode': 'Train', 'source': 'Configured train fare rates', 'source_type': 'CONFIGURED_ESTIMATE', 'currency': 'INR', 'distance_km': float(distance), 'distance': distance_info, 'fares': fares, 'selected_class': selected_class, 'price': selected['party_total'], 'warnings': [config['note']]}
    except (ValueError, KeyError, OSError):
        return unavailable('Train fare configuration invalid or unavailable')


def search_train_transport(origin, destination, passengers=1, selected_class='3A', supplied_distance=None):
    if is_local_mobility(origin, destination):
        return unavailable('Local mobility is excluded from inter-city transport. No fare calculated.')
    distance = calculate_distance(origin, destination, supplied_distance)
    return estimate_train_fares(distance, passengers, selected_class)
