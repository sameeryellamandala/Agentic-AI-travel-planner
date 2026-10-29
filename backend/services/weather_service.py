"""Exact local-calendar date forecast. No derived or fabricated weather values."""
import os
from datetime import date as calendar_date, datetime, timezone, timedelta
import requests


def get_weather(location, date=None):
    base = {'source':'OpenWeather', 'location':location, 'date':date}
    def fail(reason):
        return {**base, 'success':False, 'status':'UNAVAILABLE', 'source_type':'UNAVAILABLE', 'reason':reason}
    try:
        target = calendar_date.fromisoformat(date or '')
    except ValueError:
        return fail('Exact date in YYYY-MM-DD format is required')
    if not location.strip():
        return fail('Location is required')
    key = os.getenv('OPENWEATHER_API_KEY')
    if not key:
        return fail('OPENWEATHER_API_KEY is not configured')
    try:
        response = requests.get('https://api.openweathermap.org/data/2.5/forecast', params={'q':location, 'appid':key, 'units':'metric'}, timeout=15)
        if response.status_code != 200:
            return fail(f'OpenWeather HTTP {response.status_code}')
        data = response.json()
        offset = data.get('city',{}).get('timezone')
        if offset is None:
            return fail('Provider location timezone unavailable')
        slots = []
        for slot in data.get('list',[]):
            local = datetime.fromtimestamp(slot['dt'],timezone.utc)+timedelta(seconds=offset)
            if local.date()==target:
                slots.append((abs(local.hour-12),slot))
        if not slots:
            return fail('Requested local date is outside the available five-day forecast window')
        slot = min(slots,key=lambda x:x[0])[1]
        main = slot.get('main',{})
        if main.get('temp') is None:
            return fail('Provider temperature unavailable')
        conditions = (slot.get('weather') or [{}])[0]
        return {**base, 'success':True, 'status':'SUCCESS', 'source_type':'LIVE_PROVIDER',
            'temperature':main['temp'], 'feels_like':main.get('feels_like'), 'condition':conditions.get('main'),
            'description':conditions.get('description'), 'humidity':main.get('humidity'),
            'wind_speed':slot.get('wind',{}).get('speed'),
            'rain_probability': None if slot.get('pop') is None else f"{slot['pop']*100:g}%",
            'forecast_timestamp_utc':slot['dt'], 'timezone_offset_seconds':offset}
    except (requests.RequestException, ValueError, TypeError, KeyError, OverflowError):
        return fail('OpenWeather request or response failed')

get_live_weather = get_weather
