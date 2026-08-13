"""
Extracción de características de destinos turísticos desde Wikipedia API.

Obtiene descripción, coordenadas y datos estáticos enriquecidos para cada
destino del modelo de recomendación. Incluye fallback a Wikipedia en inglés.

API ES: https://es.wikipedia.org/api/rest_v1/page/summary/{destino}
API EN: https://en.wikipedia.org/api/rest_v1/page/summary/{destino}

Ejecución:
    cd /d D:\\Master\\TrabajoFinalUCM\\TFM
    python scripts/extract_destination_features.py
    python scripts/extract_destination_features.py --db data/tui_recomendador.db
    python scripts/extract_destination_features.py --help
"""

import argparse
import json
import sqlite3
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

# Asegurar imports del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Datos maestros de destinos con metadatos hardcodeados
# ---------------------------------------------------------------------------

DESTINOS_INFO = {
    "Mallorca": {
        "pais": "España", "zona_geografica": "Mediterráneo",
        "lat": 39.5696, "lon": 2.6502,
        "categorias": ["playa", "cultura", "naturaleza", "gastronomia"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": True,
        "clima_predominante": "mediterráneo", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.6,
        "poblacion_estimada": 920000, "nivel_saturacion_conocido": "alto",
        "wikipedia_title_es": "Mallorca", "wikipedia_title_en": "Mallorca",
    },
    "Tenerife": {
        "pais": "España", "zona_geografica": "Atlántico",
        "lat": 28.2916, "lon": -16.6291,
        "categorias": ["playa", "naturaleza", "aventura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": True,
        "clima_predominante": "subtropical", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.7,
        "poblacion_estimada": 930000, "nivel_saturacion_conocido": "alto",
        "wikipedia_title_es": "Tenerife", "wikipedia_title_en": "Tenerife",
    },
    "Ibiza": {
        "pais": "España", "zona_geografica": "Mediterráneo",
        "lat": 38.9067, "lon": 1.4206,
        "categorias": ["playa", "bienestar", "gastronomia"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": True,
        "clima_predominante": "mediterráneo", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.7,
        "poblacion_estimada": 150000, "nivel_saturacion_conocido": "muy_alto",
        "wikipedia_title_es": "Ibiza", "wikipedia_title_en": "Ibiza",
    },
    "Costa del Sol": {
        "pais": "España", "zona_geografica": "Mediterráneo",
        "lat": 36.7213, "lon": -4.4214,
        "categorias": ["playa", "gastronomia", "cultura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": False,
        "clima_predominante": "mediterráneo", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.4,
        "poblacion_estimada": 600000, "nivel_saturacion_conocido": "alto",
        "wikipedia_title_es": "Costa del Sol", "wikipedia_title_en": "Costa del Sol",
    },
    "Barcelona": {
        "pais": "España", "zona_geografica": "Mediterráneo",
        "lat": 41.3874, "lon": 2.1686,
        "categorias": ["cultura", "gastronomia", "playa", "aventura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "mediterráneo", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.5,
        "poblacion_estimada": 1620000, "nivel_saturacion_conocido": "muy_alto",
        "wikipedia_title_es": "Barcelona", "wikipedia_title_en": "Barcelona",
    },
    "Madrid": {
        "pais": "España", "zona_geografica": "Interior",
        "lat": 40.4168, "lon": -3.7038,
        "categorias": ["cultura", "gastronomia", "aventura"],
        "tiene_playa": False, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "continental_mediterráneo", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.3,
        "poblacion_estimada": 3280000, "nivel_saturacion_conocido": "alto",
        "wikipedia_title_es": "Madrid", "wikipedia_title_en": "Madrid",
    },
    "Málaga": {
        "pais": "España", "zona_geografica": "Mediterráneo",
        "lat": 36.7213, "lon": -4.4214,
        "categorias": ["playa", "cultura", "gastronomia"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": False,
        "clima_predominante": "mediterráneo", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.4,
        "poblacion_estimada": 580000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Málaga", "wikipedia_title_en": "Málaga",
    },
    "Sevilla": {
        "pais": "España", "zona_geografica": "Interior",
        "lat": 37.3891, "lon": -5.9845,
        "categorias": ["cultura", "gastronomia", "aventura"],
        "tiene_playa": False, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "mediterráneo_continental", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.3,
        "poblacion_estimada": 690000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Sevilla", "wikipedia_title_en": "Seville",
    },
    "Valencia": {
        "pais": "España", "zona_geografica": "Mediterráneo",
        "lat": 39.4699, "lon": -0.3763,
        "categorias": ["playa", "cultura", "gastronomia", "naturaleza"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "mediterráneo", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.4,
        "poblacion_estimada": 800000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Valencia", "wikipedia_title_en": "Valencia",
    },
    "Gran Canaria": {
        "pais": "España", "zona_geografica": "Atlántico",
        "lat": 27.9202, "lon": -15.5474,
        "categorias": ["playa", "naturaleza", "aventura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": True,
        "clima_predominante": "subtropical", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.7,
        "poblacion_estimada": 860000, "nivel_saturacion_conocido": "alto",
        "wikipedia_title_es": "Gran Canaria", "wikipedia_title_en": "Gran Canaria",
    },
    "Alicante": {
        "pais": "España", "zona_geografica": "Mediterráneo",
        "lat": 38.3452, "lon": -0.4810,
        "categorias": ["playa", "cultura", "gastronomia"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": False,
        "clima_predominante": "mediterráneo", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.4,
        "poblacion_estimada": 340000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Alicante", "wikipedia_title_en": "Alicante",
    },
    "Bilbao": {
        "pais": "España", "zona_geografica": "Atlántico",
        "lat": 43.2630, "lon": -2.9350,
        "categorias": ["cultura", "gastronomia", "naturaleza"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "oceánico", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.3,
        "poblacion_estimada": 350000, "nivel_saturacion_conocido": "bajo",
        "wikipedia_title_es": "Bilbao", "wikipedia_title_en": "Bilbao",
    },
    "San Sebastián": {
        "pais": "España", "zona_geografica": "Atlántico",
        "lat": 43.3183, "lon": -1.9812,
        "categorias": ["gastronomia", "playa", "cultura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": False,
        "clima_predominante": "oceánico", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.4,
        "poblacion_estimada": 187000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "San Sebastián (Guipúzcoa)", "wikipedia_title_en": "San Sebastián",
    },
    "Córdoba": {
        "pais": "España", "zona_geografica": "Interior",
        "lat": 37.8882, "lon": -4.7794,
        "categorias": ["cultura", "gastronomia"],
        "tiene_playa": False, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "mediterráneo_continental", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.3,
        "poblacion_estimada": 325000, "nivel_saturacion_conocido": "bajo",
        "wikipedia_title_es": "Córdoba (España)", "wikipedia_title_en": "Córdoba, Spain",
    },
    "Granada": {
        "pais": "España", "zona_geografica": "Interior",
        "lat": 37.1773, "lon": -3.5986,
        "categorias": ["cultura", "naturaleza", "aventura"],
        "tiene_playa": False, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "mediterráneo_continental", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.4,
        "poblacion_estimada": 232000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Granada", "wikipedia_title_en": "Granada",
    },
    "Cádiz": {
        "pais": "España", "zona_geografica": "Atlántico",
        "lat": 36.5271, "lon": -6.2886,
        "categorias": ["playa", "cultura", "gastronomia"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": False,
        "clima_predominante": "mediterráneo_oceánico", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.5,
        "poblacion_estimada": 116000, "nivel_saturacion_conocido": "bajo",
        "wikipedia_title_es": "Cádiz", "wikipedia_title_en": "Cádiz",
    },
    "Fuerteventura": {
        "pais": "España", "zona_geografica": "Atlántico",
        "lat": 28.3587, "lon": -14.0538,
        "categorias": ["playa", "naturaleza", "aventura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": True,
        "clima_predominante": "subtropical_árido", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.8,
        "poblacion_estimada": 120000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Fuerteventura", "wikipedia_title_en": "Fuerteventura",
    },
    "Lanzarote": {
        "pais": "España", "zona_geografica": "Atlántico",
        "lat": 29.0469, "lon": -13.5900,
        "categorias": ["playa", "naturaleza", "cultura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": True,
        "clima_predominante": "subtropical_árido", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.8,
        "poblacion_estimada": 155000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Lanzarote", "wikipedia_title_en": "Lanzarote",
    },
    "Menorca": {
        "pais": "España", "zona_geografica": "Mediterráneo",
        "lat": 39.9496, "lon": 4.1104,
        "categorias": ["playa", "naturaleza", "cultura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": True,
        "clima_predominante": "mediterráneo", "idioma_principal": "español",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.8,
        "poblacion_estimada": 96000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Menorca", "wikipedia_title_en": "Menorca",
    },
    "Antalya": {
        "pais": "Turquía", "zona_geografica": "Mediterráneo",
        "lat": 36.8969, "lon": 30.7133,
        "categorias": ["playa", "cultura", "aventura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "mediterráneo", "idioma_principal": "turco",
        "moneda": "TRY", "accesibilidad": 3, "sensibilidad_ambiental": 0.4,
        "poblacion_estimada": 2500000, "nivel_saturacion_conocido": "alto",
        "wikipedia_title_es": "Antalya", "wikipedia_title_en": "Antalya",
    },
    "Rodas": {
        "pais": "Grecia", "zona_geografica": "Mediterráneo",
        "lat": 36.4349, "lon": 28.2176,
        "categorias": ["playa", "cultura", "naturaleza"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": True,
        "clima_predominante": "mediterráneo", "idioma_principal": "griego",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.6,
        "poblacion_estimada": 120000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Rodas", "wikipedia_title_en": "Rhodes",
    },
    "Santorini": {
        "pais": "Grecia", "zona_geografica": "Mediterráneo",
        "lat": 36.3932, "lon": 25.4615,
        "categorias": ["cultura", "playa", "gastronomia", "bienestar"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": True,
        "clima_predominante": "mediterráneo", "idioma_principal": "griego",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.8,
        "poblacion_estimada": 15500, "nivel_saturacion_conocido": "muy_alto",
        "wikipedia_title_es": "Santorini", "wikipedia_title_en": "Santorini",
    },
    "Hurghada": {
        "pais": "Egipto", "zona_geografica": "Mar Rojo",
        "lat": 27.2579, "lon": 33.8116,
        "categorias": ["playa", "aventura", "naturaleza"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": False,
        "clima_predominante": "desértico_cálido", "idioma_principal": "árabe",
        "moneda": "EGP", "accesibilidad": 2, "sensibilidad_ambiental": 0.7,
        "poblacion_estimada": 260000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Hurghada", "wikipedia_title_en": "Hurghada",
    },
    "Punta Cana": {
        "pais": "República Dominicana", "zona_geografica": "Caribe",
        "lat": 18.5601, "lon": -68.3725,
        "categorias": ["playa", "bienestar", "aventura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": True,
        "clima_predominante": "tropical", "idioma_principal": "español",
        "moneda": "DOP", "accesibilidad": 2, "sensibilidad_ambiental": 0.6,
        "poblacion_estimada": 100000, "nivel_saturacion_conocido": "alto",
        "wikipedia_title_es": "Punta Cana", "wikipedia_title_en": "Punta Cana",
    },
    "Cancún": {
        "pais": "México", "zona_geografica": "Caribe",
        "lat": 21.1619, "lon": -86.8515,
        "categorias": ["playa", "aventura", "cultura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "tropical", "idioma_principal": "español",
        "moneda": "MXN", "accesibilidad": 3, "sensibilidad_ambiental": 0.7,
        "poblacion_estimada": 890000, "nivel_saturacion_conocido": "muy_alto",
        "wikipedia_title_es": "Cancún", "wikipedia_title_en": "Cancún",
    },
    "Riviera Maya": {
        "pais": "México", "zona_geografica": "Caribe",
        "lat": 20.6296, "lon": -87.0739,
        "categorias": ["playa", "cultura", "aventura", "naturaleza"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "tropical", "idioma_principal": "español",
        "moneda": "MXN", "accesibilidad": 2, "sensibilidad_ambiental": 0.8,
        "poblacion_estimada": 50000, "nivel_saturacion_conocido": "alto",
        "wikipedia_title_es": "Riviera Maya", "wikipedia_title_en": "Riviera Maya",
    },
    "Dubái": {
        "pais": "Emiratos Árabes Unidos", "zona_geografica": "Golfo Pérsico",
        "lat": 25.2048, "lon": 55.2708,
        "categorias": ["bienestar", "cultura", "aventura", "gastronomia"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": False,
        "clima_predominante": "desértico_cálido", "idioma_principal": "árabe",
        "moneda": "AED", "accesibilidad": 3, "sensibilidad_ambiental": 0.3,
        "poblacion_estimada": 3400000, "nivel_saturacion_conocido": "alto",
        "wikipedia_title_es": "Dubái", "wikipedia_title_en": "Dubai",
    },
    "Maldivas": {
        "pais": "Maldivas", "zona_geografica": "Océano Índico",
        "lat": 3.2028, "lon": 73.2207,
        "categorias": ["playa", "bienestar", "naturaleza"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": True,
        "clima_predominante": "tropical_monzónico", "idioma_principal": "maldivo",
        "moneda": "MVR", "accesibilidad": 1, "sensibilidad_ambiental": 0.9,
        "poblacion_estimada": 560000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Maldivas", "wikipedia_title_en": "Maldives",
    },
    "Bali": {
        "pais": "Indonesia", "zona_geografica": "Sudeste Asiático",
        "lat": -8.3405, "lon": 115.0920,
        "categorias": ["cultura", "playa", "bienestar", "naturaleza"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": True,
        "clima_predominante": "tropical", "idioma_principal": "indonesio",
        "moneda": "IDR", "accesibilidad": 2, "sensibilidad_ambiental": 0.7,
        "poblacion_estimada": 4300000, "nivel_saturacion_conocido": "alto",
        "wikipedia_title_es": "Bali", "wikipedia_title_en": "Bali",
    },
    "Phuket": {
        "pais": "Tailandia", "zona_geografica": "Sudeste Asiático",
        "lat": 7.8804, "lon": 98.3923,
        "categorias": ["playa", "cultura", "aventura", "gastronomia"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": True,
        "clima_predominante": "tropical_monzónico", "idioma_principal": "tailandés",
        "moneda": "THB", "accesibilidad": 2, "sensibilidad_ambiental": 0.6,
        "poblacion_estimada": 400000, "nivel_saturacion_conocido": "alto",
        "wikipedia_title_es": "Phuket", "wikipedia_title_en": "Phuket",
    },
    "Marrakech": {
        "pais": "Marruecos", "zona_geografica": "Norte de África",
        "lat": 31.6295, "lon": -7.9811,
        "categorias": ["cultura", "aventura", "gastronomia", "naturaleza"],
        "tiene_playa": False, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "semiárido", "idioma_principal": "árabe",
        "moneda": "MAD", "accesibilidad": 2, "sensibilidad_ambiental": 0.5,
        "poblacion_estimada": 930000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Marrakech", "wikipedia_title_en": "Marrakesh",
    },
    "Cabo Verde": {
        "pais": "Cabo Verde", "zona_geografica": "Atlántico",
        "lat": 14.9330, "lon": -23.5133,
        "categorias": ["playa", "naturaleza", "aventura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": True,
        "clima_predominante": "tropical_seco", "idioma_principal": "portugués",
        "moneda": "CVE", "accesibilidad": 1, "sensibilidad_ambiental": 0.8,
        "poblacion_estimada": 590000, "nivel_saturacion_conocido": "bajo",
        "wikipedia_title_es": "Cabo Verde", "wikipedia_title_en": "Cape Verde",
    },
    "Split": {
        "pais": "Croacia", "zona_geografica": "Mediterráneo",
        "lat": 43.5081, "lon": 16.4402,
        "categorias": ["playa", "cultura", "naturaleza", "gastronomia"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "mediterráneo", "idioma_principal": "croata",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.6,
        "poblacion_estimada": 170000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Split", "wikipedia_title_en": "Split, Croatia",
    },
    "Creta": {
        "pais": "Grecia", "zona_geografica": "Mediterráneo",
        "lat": 35.2401, "lon": 24.4691,
        "categorias": ["playa", "cultura", "naturaleza", "gastronomia"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": True,
        "clima_predominante": "mediterráneo", "idioma_principal": "griego",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.5,
        "poblacion_estimada": 630000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Creta", "wikipedia_title_en": "Crete",
    },
    "Sicilia": {
        "pais": "Italia", "zona_geografica": "Mediterráneo",
        "lat": 37.5994, "lon": 14.0154,
        "categorias": ["cultura", "playa", "gastronomia", "naturaleza"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": True,
        "clima_predominante": "mediterráneo", "idioma_principal": "italiano",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.5,
        "poblacion_estimada": 5000000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Sicilia", "wikipedia_title_en": "Sicily",
    },
    "Cerdeña": {
        "pais": "Italia", "zona_geografica": "Mediterráneo",
        "lat": 40.1209, "lon": 9.0129,
        "categorias": ["playa", "naturaleza", "cultura", "gastronomia"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": True,
        "clima_predominante": "mediterráneo", "idioma_principal": "italiano",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.7,
        "poblacion_estimada": 1640000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Cerdeña", "wikipedia_title_en": "Sardinia",
    },
    "Costa Amalfitana": {
        "pais": "Italia", "zona_geografica": "Mediterráneo",
        "lat": 40.6333, "lon": 14.6029,
        "categorias": ["cultura", "gastronomia", "playa", "bienestar"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "mediterráneo", "idioma_principal": "italiano",
        "moneda": "EUR", "accesibilidad": 2, "sensibilidad_ambiental": 0.8,
        "poblacion_estimada": 50000, "nivel_saturacion_conocido": "alto",
        "wikipedia_title_es": "Costa amalfitana", "wikipedia_title_en": "Amalfi Coast",
    },
    "Algarve": {
        "pais": "Portugal", "zona_geografica": "Atlántico",
        "lat": 37.0179, "lon": -7.9304,
        "categorias": ["playa", "naturaleza", "gastronomia", "cultura"],
        "tiene_playa": True, "tiene_patrimonio_unesco": False, "es_isla": False,
        "clima_predominante": "mediterráneo", "idioma_principal": "portugués",
        "moneda": "EUR", "accesibilidad": 3, "sensibilidad_ambiental": 0.5,
        "poblacion_estimada": 450000, "nivel_saturacion_conocido": "medio",
        "wikipedia_title_es": "Algarve", "wikipedia_title_en": "Algarve",
    },
    "Túnez": {
        "pais": "Túnez", "zona_geografica": "Norte de África",
        "lat": 36.8065, "lon": 10.1815,
        "categorias": ["cultura", "playa", "aventura", "gastronomia"],
        "tiene_playa": True, "tiene_patrimonio_unesco": True, "es_isla": False,
        "clima_predominante": "mediterráneo", "idioma_principal": "árabe",
        "moneda": "TND", "accesibilidad": 2, "sensibilidad_ambiental": 0.4,
        "poblacion_estimada": 12000000, "nivel_saturacion_conocido": "bajo",
        "wikipedia_title_es": "Túnez", "wikipedia_title_en": "Tunisia",
    },
}

# ---------------------------------------------------------------------------
# Wikipedia API
# ---------------------------------------------------------------------------

WIKIPEDIA_API_ES = "https://es.wikipedia.org/api/rest_v1/page/summary"
WIKIPEDIA_API_EN = "https://en.wikipedia.org/api/rest_v1/page/summary"


# ---------------------------------------------------------------------------
# Funciones
# ---------------------------------------------------------------------------

def crear_tabla(conn: sqlite3.Connection) -> None:
    """Crea la tabla destinos_caracteristicas si no existe."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS destinos_caracteristicas (
            id TEXT PRIMARY KEY,
            destino_nombre TEXT NOT NULL UNIQUE,
            pais TEXT NOT NULL,
            zona_geografica TEXT NOT NULL,
            latitud REAL NOT NULL,
            longitud REAL NOT NULL,
            descripcion_wikipedia TEXT,
            categorias_principales TEXT,
            poblacion_estimada INTEGER,
            tiene_playa INTEGER NOT NULL DEFAULT 0,
            tiene_patrimonio_unesco INTEGER NOT NULL DEFAULT 0,
            es_isla INTEGER NOT NULL DEFAULT 0,
            clima_predominante TEXT,
            idioma_principal TEXT,
            moneda TEXT,
            accesibilidad_estimada INTEGER NOT NULL DEFAULT 2,
            sensibilidad_ambiental REAL NOT NULL DEFAULT 0.5,
            nivel_saturacion_conocido TEXT,
            fecha_extraccion TEXT NOT NULL
        )
    """)
    conn.commit()


def existe_destino(conn: sqlite3.Connection, destino: str) -> bool:
    """Verifica si ya existe el destino en la tabla."""
    cursor = conn.execute(
        "SELECT 1 FROM destinos_caracteristicas WHERE destino_nombre = ?",
        (destino,)
    )
    return cursor.fetchone() is not None


def obtener_descripcion_wikipedia(titulo_es: str, titulo_en: str) -> str | None:
    """
    Obtiene el extracto de Wikipedia. Intenta primero en español,
    si falla usa fallback en inglés.
    """
    headers = {
        "User-Agent": "TUI-Recomendador-TFM/1.0 (Universidad Complutense de Madrid)",
        "Accept": "application/json",
    }

    # Intentar español primero
    url_es = f"{WIKIPEDIA_API_ES}/{titulo_es}"
    try:
        resp = requests.get(url_es, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            extract = data.get("extract")
            if extract and len(extract) > 20:
                return extract
    except (requests.RequestException, ValueError):
        pass

    # Fallback: inglés
    url_en = f"{WIKIPEDIA_API_EN}/{titulo_en}"
    try:
        resp = requests.get(url_en, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            extract = data.get("extract")
            if extract and len(extract) > 20:
                return extract
    except (requests.RequestException, ValueError):
        pass

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Extracción de características de destinos desde Wikipedia + datos estáticos"
    )
    parser.add_argument(
        "--db", type=str, default="data/tui_recomendador.db",
        help="Ruta a la base de datos SQLite (default: data/tui_recomendador.db)"
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / args.db

    if not db_path.parent.exists():
        print(f"[ERROR] Directorio no encontrado: {db_path.parent}")
        sys.exit(1)

    print("=" * 70)
    print("EXTRACCIÓN DE CARACTERÍSTICAS DE DESTINOS - Wikipedia API")
    print("=" * 70)
    print(f"Base de datos: {db_path}")
    print(f"Destinos a procesar: {len(DESTINOS_INFO)}")
    print()

    conn = sqlite3.connect(str(db_path))
    crear_tabla(conn)

    total_insertados = 0
    total_duplicados = 0
    total_wiki_ok = 0

    for idx, (destino, info) in enumerate(DESTINOS_INFO.items(), 1):
        print(f"[{idx}/{len(DESTINOS_INFO)}] {destino}...")

        if existe_destino(conn, destino):
            print(f"  -> Ya existe, saltando")
            total_duplicados += 1
            continue

        # Obtener descripción de Wikipedia (con fallback inglés)
        titulo_es = info.get("wikipedia_title_es", destino)
        titulo_en = info.get("wikipedia_title_en", destino)

        try:
            descripcion = obtener_descripcion_wikipedia(titulo_es, titulo_en)
        except Exception as e:
            print(f"  [ERROR] Wikipedia: {e}")
            descripcion = None

        if descripcion:
            total_wiki_ok += 1
            print(f"  -> Wikipedia OK ({len(descripcion)} chars)")
        else:
            print(f"  -> Wikipedia: sin extracto disponible")

        # Insertar registro
        categorias_json = json.dumps(info["categorias"], ensure_ascii=False)

        try:
            conn.execute("""
                INSERT INTO destinos_caracteristicas
                (id, destino_nombre, pais, zona_geografica, latitud, longitud,
                 descripcion_wikipedia, categorias_principales, poblacion_estimada,
                 tiene_playa, tiene_patrimonio_unesco, es_isla,
                 clima_predominante, idioma_principal, moneda,
                 accesibilidad_estimada, sensibilidad_ambiental,
                 nivel_saturacion_conocido, fecha_extraccion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                destino, info["pais"], info["zona_geografica"],
                info["lat"], info["lon"],
                descripcion, categorias_json, info["poblacion_estimada"],
                int(info["tiene_playa"]), int(info["tiene_patrimonio_unesco"]),
                int(info["es_isla"]),
                info["clima_predominante"], info["idioma_principal"], info["moneda"],
                info["accesibilidad"], info["sensibilidad_ambiental"],
                info["nivel_saturacion_conocido"],
                datetime.now().isoformat()
            ))
            total_insertados += 1
        except sqlite3.IntegrityError:
            total_duplicados += 1
            print(f"  -> Conflicto de integridad, saltando")

        # Pausa entre llamadas a Wikipedia
        time.sleep(1.0)

    conn.commit()
    conn.close()

    # Resumen final
    print()
    print("=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    print(f"✓ Total insertados: {total_insertados} registros en tabla destinos_caracteristicas")
    print(f"  Duplicados descartados: {total_duplicados}")
    print(f"  Wikipedia exitoso: {total_wiki_ok}/{total_insertados} destinos")
    print(f"  Destinos totales procesados: {len(DESTINOS_INFO)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
