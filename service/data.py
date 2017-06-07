# -*- coding: utf-8 -*-
import os
import re
import requests
from elasticsearch import Elasticsearch


def query(address, params=None):
    matches = search_es(address, params)
    return matches if matches else search_osm(address)


def search_es(address, params):
    es = Elasticsearch()
    terms = []
    query = {'query': {'bool': {'must': terms}}}
    road, number = get_parts_from(address.split(',')[0])
    terms.append({'match_phrase_prefix': {'nomenclatura': road}})
    if params and (len(params)) > 1:
        locality = params.get('localidad')
        state = params.get('provincia')
        if locality:
            terms.append({'match': {'localidad': locality}})
        if state:
            terms.append({'match': {'provincia': state}})
    result = es.search(body=query)
    addresses = [parse_es(hit) for hit in result['hits']['hits']]
    if addresses and number:
        addresses = process_door(number, addresses)
    return addresses


def search_osm(address):
    url = os.environ.get('OSM_API_URL')
    params = {
        'q': address,
        'format': 'json',
        'countrycodes': 'ar',
        'addressdetails': 1,
        'limit': 10
    }
    result = requests.get(url, params=params).json()
    return [parse_osm(match) for match in result]


def parse_es(result):
    obs = {
        'fuente': 'INDEC',
        'info': 'Se procesó correctamente la dirección buscada.'
        }
    result['_source'].update(observaciones=obs)
    return result['_source']


def parse_osm(result):
    return {
        'nomenclatura': result['display_name'],
        'nombre': result['address'].get('road'),
        'tipo': result['type'],
        'altura_inicial': None,
        'altura_final': None,
        'localidad': result['address'].get('city'),
        'provincia': result['address'].get('state'),
        'observaciones': {
            'fuente': 'OSM',
            'info': result['type']
            }
        }


def get_parts_from(address):
    match = re.search(r'(\s[0-9]+?)$', address)
    number = int(match.group(1)) if match else None
    address = re.sub(r'(\s[0-9]+?)$', r'', address)
    return address.strip(), number


def process_door(number, addresses):
    for address in addresses:
        info = address['observaciones']['info']
        st_start = address.get('altura_inicial')
        st_end = address.get('altura_final')
        if st_start and st_end:
            if st_start <= number and number <= st_end:
                parts = address['nomenclatura'].split(',')
                parts[0] += ' %s' % str(number)
                address['nomenclatura'] = ', '.join(parts)
            else:
                info = 'La altura buscada está fuera del rango conocido.'
        else:
            info = 'La calle no tiene numeración en la base de datos.'
        address['observaciones']['info'] = info
    return addresses